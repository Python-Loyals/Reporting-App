import datetime
import flask as fl
import flask_login
import auth
from os.path import join, dirname
from urllib.parse import quote, unquote
from reporting_app import util
from config import reporting_app_config as cfg, project_status as project_status_cfg
from rest_api import settings

app = fl.Flask(__name__)
app.secret_key = cfg['key'].encode()
login_manager = flask_login.LoginManager()
login_manager.init_app(app)
version = open(join(dirname(dirname(__file__)), 'version.txt')).read()


def rest_api():
    return flask_login.current_user.comm


def _now():
    return datetime.datetime.now()


def render_template(template, title=None, **context):
    return fl.render_template(template, title=title, version=version, **context)


@login_manager.user_loader
def load_user(user_id):
    return auth.User.get(user_id)


@login_manager.unauthorized_handler
def unauthorised_handler():
    return fl.redirect('/login?redirect=' + quote(fl.request.full_path, safe=()))


@login_manager.token_loader
def load_token(token_hash):
    uid = auth.check_login_token(token_hash)
    if uid:
        return auth.User.get(uid)


@app.route('/')
@flask_login.login_required
def main_page():
    return render_template('main_page.html', 'Main Page')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if fl.request.method == 'GET':
        return render_template(
            'login.html',
            'Login',
            message='Welcome to the EGCG Reporting App. Log in here.',
            redirect=quote(fl.request.args.get('redirect', ''), safe=())
        )

    username = fl.request.form['username']
    redirect = fl.request.form['redirect']
    if auth.check_user_auth(username, fl.request.form['pw']):
        u = auth.User(username)
        flask_login.login_user(u, remember=True)
        app.logger.info("Logged in user '%s'", username)
        return fl.redirect(unquote(redirect))

    return render_template(
        'login.html',
        'Login',
        message='Bad login.',
        redirect=redirect
    )


@app.route('/logout')
def logout():
    flask_login.logout_user()
    return render_template('login.html', 'Logout', message='Logged out.')


@app.route('/change_password', methods=['GET', 'POST'])
@flask_login.login_required
def change_password():
    if fl.request.method == 'GET':
        return render_template('change_password.html', 'Change Password')

    user_id = flask_login.current_user.username
    form = fl.request.form
    if auth.change_pw(user_id, form['old_pw'], form['new_pw']):
        return fl.redirect('/logout')
    return render_template('login.html', 'Login', message='Bad request.')


@app.route('/runs/<view_type>')
@flask_login.login_required
def runs_report(view_type):
    ajax_call = {'func_name': 'merge_multi_sources', 'merge_on': 'run_id'}

    if view_type == 'all':
        ajax_call['api_urls'] = [
            util.construct_url('runs', max_results=10000),
            util.construct_url('lims/run_status'),
        ]

    elif view_type in ['recent', 'current_year', 'year_to_date']:
        if view_type == 'recent':
            time_ago = _now() - datetime.timedelta(days=30)
        elif view_type == 'year_to_date':
            time_ago = _now() - datetime.timedelta(days=365)
        elif view_type == 'current_year':
            y = _now().year
            time_ago = datetime.datetime(year=y, month=1, day=1)
            view_type = str(y)

        ajax_call['api_urls'] = [
            util.construct_url('runs', where={'_created': {'$gte': time_ago.strftime(settings.DATE_FORMAT)}}, max_results=10000),
            util.construct_url('lims/run_status', createddate=time_ago.strftime(settings.DATE_FORMAT)),
        ]

    else:
        fl.abort(404)
        return None

    title = util.capitalise(view_type).replace('_', ' ') + ' Runs'

    return render_template(
        'untabbed_datatables.html',
        title,
        include_review_modal=True,
        table=util.datatable_cfg(
            title,
            'runs',
            ajax_call=ajax_call,
            create_row='color_filter',
            fixed_header=True,
            review={'entity_field': 'sample_ids', 'button_name': 'runreview'}
        )
    )


@app.route('/run/<run_id>')
@flask_login.login_required
def report_run(run_id):
    lanes = sorted(set(e['lane_number'] for e in rest_api().get_documents('lanes', where={'run_id': run_id})))

    return render_template(
        'run_report.html',
        run_id + ' Run Report',
        include_review_modal=True,
        lane_aggregation=util.datatable_cfg(
            'Aggregation per lane',
            'lane_aggregation',
            api_url=util.construct_url('lanes', where={'run_id': run_id}),
            default_sort_col='lane_number',
            minimal=True,
            create_row='color_filter',
            review={'entity_field': 'aggregated.sample_ids', 'button_name': 'runreview'}
        ),
        tab_sets=[
            util.tab_set_cfg(
                'Demultiplexing reports per lane',
                [
                    util.datatable_cfg(
                        'Demultiplexing lane ' + str(lane),
                        'demultiplexing',
                        api_url=util.construct_url('run_elements', where={'run_id': run_id, 'lane': lane}),
                        minimal=True,
                        create_row='color_filter',
                        review={'entity_field': 'sample_id', 'button_name': 'runreview'}
                    )
                    for lane in lanes
                ]
            ),
            util.tab_set_cfg(
                'Unexpected barcodes',
                [
                    util.datatable_cfg(
                        'Unexpected barcodes lane ' + str(lane),
                        'unexpected_barcodes',
                        api_url=util.construct_url('unexpected_barcodes', where={'run_id': run_id, 'lane': lane}),
                        default_sort_col='passing_filter_reads',
                        minimal=True,
                        create_row='color_filter'
                    )
                    for lane in lanes
                ]
            )
        ],
        procs=rest_api().get_documents(
            'analysis_driver_procs',
            where={'dataset_type': 'run', 'dataset_name': run_id},
            embedded={'stages': 1},
            sort='-_created'
        )
    )


@app.route('/projects/')
@flask_login.login_required
def project_reports():
    return render_template(
        'untabbed_datatables.html',
        'Projects',
        table=util.datatable_cfg(
            'All projects list',
            'projects',
            ajax_call={
                'func_name': 'merge_multi_sources',
                'api_urls': [
                    util.construct_url('projects', max_results=10000),
                    util.construct_url('lims/project_info', match={'project_status': 'all'}),
                ],
                'merge_on': 'project_id'
            }
        )
    )


@app.route('/samples/<view_type>')
@flask_login.login_required
def report_samples(view_type):
    six_months_ago = _now() - datetime.timedelta(days=182)
    ajax_call = {'func_name': 'merge_multi_sources_keep_first', 'merge_on': 'sample_id'}

    if view_type == 'all':
        title = 'All samples'
        ajax_call['api_urls'] = [
            util.construct_url('samples', max_results=10000),
            util.construct_url('lims/sample_status', match={'project_status': 'all'}),
            util.construct_url('lims/sample_info', match={'project_status': 'all'})
        ]
    elif view_type == 'processing':
        title = 'Samples processing'
        ajax_call['api_urls'] = [
            util.construct_url('samples', where={'aggregated.most_recent_proc.status': 'processing'}, max_results=10000),
            util.construct_url('lims/sample_status', match={'createddate': six_months_ago.strftime(settings.DATE_FORMAT), 'project_status': 'open'}),
            util.construct_url('lims/sample_info', match={'createddate': six_months_ago.strftime(settings.DATE_FORMAT), 'project_status': 'open'})
        ]
    elif view_type == 'toreview':
        title = 'Samples to review'
        ajax_call['api_urls'] = [
            util.construct_url('samples', where={'useable': 'not%20marked', 'aggregated.most_recent_proc.status': 'finished'}, max_results=10000),
            util.construct_url('lims/sample_status', match={'createddate': six_months_ago.strftime(settings.DATE_FORMAT), 'project_status': 'open'}),
            util.construct_url('lims/sample_info', match={'createddate': six_months_ago.strftime(settings.DATE_FORMAT), 'project_status': 'open'})
        ]
    else:
        fl.abort(404)
        return None

    return render_template(
        'untabbed_datatables.html',
        title,
        include_review_modal=True,
        table=util.datatable_cfg(
            title,
            'samples',
            ajax_call=ajax_call,
            review={'entity_field': 'sample_id', 'button_name': 'samplereview'}
        )
    )


@app.route('/projects/<project_ids>')
@flask_login.login_required
def report_project(project_ids):
    if project_ids == 'SGP':
        id_list = []
        for p in rest_api().get_documents('lims/project_info', match={'project_status': 'all'}):
            if p['project_id'].startswith('S'):
                id_list.append(p['project_id'])
    else:
        id_list = project_ids.split(',')

    if len(id_list) > 1:
        project_status_call = {
            'ajax_call': {
                'func_name': 'merge_multi_sources',
                'merge_on': 'project_id',
                'api_urls': [
                    util.construct_url('lims/project_status', match={'project_id': i, 'project_status': 'all'})
                    for i in id_list
                ]
            }
        }
        plate_status_call = {
            'ajax_call': {
                'func_name': 'merge_multi_sources',
                'merge_on': 'plate_id',
                'api_urls': [
                    util.construct_url('lims/plate_status', match={'project_id': i, 'project_status': 'all'})
                    for i in id_list
                ]
            }
        }
    else:
        project_status_call = {
            'api_url': util.construct_url('lims/project_status', match={'project_id': id_list[0], 'project_status': 'all'})
        }
        plate_status_call = {
            'api_url': util.construct_url('lims/plate_status', match={'project_id': id_list[0], 'project_status': 'all'})
        }

    procs = []
    bioinformatics_urls = []
    for i in id_list:
        docs = rest_api().get_documents(
            'analysis_driver_procs',
            where={'dataset_type': 'project', 'dataset_name': i},
            embedded={'stages': 1},
            sort='-_created'
        )
        procs.extend(docs)

        bioinformatics_urls += [
            util.construct_url('samples', where={'project_id': i}, max_results=10000),
            util.construct_url('lims/sample_status', match={'project_id': i, 'project_status': 'all'}),
            util.construct_url('lims/sample_info', match={'project_id': i, 'project_status': 'all'})
        ]

    return render_template(
        'project_report.html',
        'Project report for ' + project_ids,
        include_review_modal=True,
        tables=[
            util.datatable_cfg(
                'Project Status for ' + project_ids,
                'project_status',
                minimal=True,
                **project_status_call
            ),
            util.datatable_cfg(
                'Plate Status for ' + project_ids,
                'plate_status',
                minimal=True,
                default_sort_col='plate_id',
                **plate_status_call
            ),
            util.datatable_cfg(
                'Bioinformatics report for ' + project_ids,
                'samples',
                ajax_call={
                    'func_name': 'merge_multi_sources',
                    'api_urls': bioinformatics_urls,
                    'merge_on': 'sample_id'
                },
                fixed_header=True,
                review={'entity_field': 'sample_id', 'button_name': 'samplereview'}
            )
        ],
        procs=procs
    )


@app.route('/sample/<sample_id>')
@flask_login.login_required
def report_sample(sample_id):
    return render_template(
        'sample_report.html',
        sample_id + ' Sample Report',
        include_review_modal=True,
        tables=[
            util.datatable_cfg(
                'Bioinformatics report for ' + sample_id,
                'samples',
                ajax_call={
                    'func_name': 'merge_multi_sources',
                    'merge_on': 'sample_id',
                    'api_urls': [
                        util.construct_url('samples', where={'sample_id': sample_id}),
                        util.construct_url('lims/sample_status', match={'sample_id': sample_id, 'project_status': 'all'}),
                        util.construct_url('lims/sample_info', match={'sample_id': sample_id, 'project_status': 'all'})
                    ]
                },
                minimal=True,
                review={'entity_field': 'sample_id', 'button_name': 'samplereview'}
            ),
            util.datatable_cfg(
                'Run elements generated for ' + sample_id,
                'sample_run_elements',
                api_url=util.construct_url('run_elements', where={'sample_id': sample_id}, max_results=1000),
                minimal=True,
                create_row='color_filter'
            )
        ],
        sample_id=sample_id,
        sample_statuses=rest_api().get_document(
            'lims/status/sample_status',
            detailed=True,
            match={'sample_id': sample_id, 'project_status': 'all'}
        ),
        lims_url=cfg['lims_url'],
        procs=rest_api().get_documents(
            'analysis_driver_procs',
            where={'dataset_type': 'sample', 'dataset_name': sample_id},
            embedded={'stages': 1},
            sort='-_created'
        )
    )


@app.route('/charts')
@flask_login.login_required
def plotting_report():
    return render_template(
        'charts.html',
        api_url=util.construct_url('run_elements', max_results=1000000),
        ajax_token=util.get_token()
    )


@app.route('/project_status', defaults={'prj_status': 'open'})
@app.route('/project_status/<prj_status>')
@flask_login.login_required
def project_status_reports(prj_status):
    status_order = []
    for s in project_status_cfg.status_order:
        status_order.append(
            {
                'name': s,
                'completed': [step for step, st in project_status_cfg.step_completed_to_status.items() if st == s],
                'queued': [step for step, st in project_status_cfg.step_queued_to_status.items() if st == s]
            }
        )

    return render_template(
        'project_status.html',
        prj_status.capitalize() + ' Project Status',
        status_order=status_order,
        table=util.datatable_cfg(
            'Status of ' + prj_status.capitalize() + ' Projects',
            'project_status',
            api_url=util.construct_url('lims/project_status', match={'project_status': prj_status}),
            state_save=True,
            fixed_header=True,
            table_foot='sum_row_per_column'
        )
    )
