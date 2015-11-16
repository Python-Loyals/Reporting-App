__author__ = 'mwham'
import argparse
import flask as fl
import os.path
import pymongo


app = fl.Flask(__name__)


col_mappings = {
    'demultiplexing': (
        {'name': 'lane',                     'title': 'Lane'},
        {'name': 'barcode',                  'title': 'Barcode'},
        {'name': 'project',                  'title': 'Project'},
        {'name': 'library_id',               'title': 'Library ID'},
        {'name': 'sample_id',                'title': 'Sample ID'},
        {'name': 'pc_pass_filter',           'title': '% Pass-filter',           'fmt': {'type': 'percentage'}},
        {'name': 'passing_filter_reads',     'title': 'Passing-filter reads',    'fmt': {'type': 'largeint'}},
        {'name': 'yield_in_gb',              'title': 'Yield (Gb)',              'fmt': {'type': 'largefloat'}},
        {'name': 'pc_q30_r1',                'title': '% Q30 R1',                'fmt': {'type': 'percentage'}},
        {'name': 'pc_q30_r2',                'title': '% Q30 R2',                'fmt': {'type': 'percentage'}}
    ),

    'unexpected_barcodes': (
        {'name': 'lane',                     'title': 'Lane'},
        {'name': 'barcode',                  'title': 'Barcode'},
        {'name': 'passing_filter_reads',     'title': 'Passing-filter reads',    'fmt': {'type': 'largeint'}},
        {'name': 'pc_reads_in_lane',         'title': '% Reads in lane',         'fmt': {'type': 'percentage'}}
    ),

    'samples': (
        {'name': 'sample_id',                'title': 'Sample ID'},
        {'name': 'library_id',               'title': 'Library ID'},
        {'name': 'user_sample_id',           'title': 'User sample ID'},
        {'name': 'yield_in_gb',              'title': 'Yield (Gb)',              'fmt': {'type': 'largefloat'}},
        {'name': 'initial_reads',            'title': 'Initial reads',           'fmt': {'type': 'largeint'}},
        {'name': 'passing_filter_reads',     'title': 'Passing-filter reads',    'fmt': {'type': 'largeint'}},
        {'name': 'nb_mapped_reads',          'title': '# mapped reads',          'fmt': {'type': 'largeint'}},
        {'name': 'pc_mapped_reads',          'title': '% mapped reads',          'fmt': {'type': 'percentage'}},
        {'name': 'nb_properly_mapped_reads', 'title': '# properly mapped reads', 'fmt': {'type': 'largeint'}},
        {'name': 'pc_properly_mapped_reads', 'title': '% properly mapped reads', 'fmt': {'type': 'percentage'}},
        {'name': 'nb_duplicate_reads',       'title': '# duplicate reads',       'fmt': {'type': 'largeint'}},
        {'name': 'pc_duplicate_reads',       'title': '% duplicate reads',       'fmt': {'type': 'percentage'}},
        {'name': 'median_coverage',          'title': 'Median coverage',         'fmt': {'type': 'largefloat'}},
        {'name': 'pc_callable',              'title': '% callable',              'fmt': {'type': 'percentage'}},
        {'name': 'pc_q30_r1',                'title': '% Q30 R1',                'fmt': {'type': 'percentage'}},
        {'name': 'pc_q30_r2',                'title': '% Q30 R2',                'fmt': {'type': 'percentage'}}
    )

}


def rest_url(extension):
    return rest_api_base + '/' + extension


@app.route('/')
def main_page():
    return fl.render_template('reports.html')


@app.route('/runs/')
def run_reports():
    runs = set(x['run_id'] for x in cli['test_db']['run_elements'].find(projection={'run_id': True}))
    return fl.render_template('runs.html', runs=runs)


@app.route('/runs/<run_id>')
def report_run(run_id):
    demultiplexing_lanes = set(x['lane'] for x in cli['test_db']['run_elements'].find(projection={'lane': True}))

    unexpected_barcode_lanes = set(x['lane'] for x in cli['test_db']['unexpected_barcodes'].find(projection={'lane': True}))

    demultiplexing_tables = []
    unexpected_barcode_tables = []
    for lane in demultiplexing_lanes:
        demultiplexing_tables.append(
            {
                'title': 'Demultiplexing data for lane ' + str(lane),
                'name': 'demultiplexing_lane_' + str(lane),
                'api_url': rest_url('run_elements?where={"run_id":"%s","lane":%s}' % (run_id, lane)),
                'cols': col_mappings['demultiplexing']
            }
        )
    for lane in unexpected_barcode_lanes:
        unexpected_barcode_tables.append(
            {
                'title': 'Unexpected barcodes for lane ' + str(lane),
                'name': 'unexpected_barcodes_lane_' + str(lane),
                'api_url': rest_url('unexpected_barcodes?where={"run_id":"%s","lane":%s}' % (run_id, lane)),
                'cols': col_mappings['unexpected_barcodes']
            }
        )

    return fl.render_template(
        'run_report.html',
        run_id=run_id,
        tab_sets=(
            {
                'name': 'demultiplexing',
                'datatables': demultiplexing_tables
            },
            {
                'name': 'unexpected_barcodes',
                'datatables': unexpected_barcode_tables
            }
        )
    )


@app.route('/runs/<run_id>/<filename>')
def serve_fastqc_report(run_id, filename):
    if '..' in filename or filename.startswith('/'):
        fl.abort(404)
        return None
    return fl.send_file(os.path.join(os.path.dirname(__file__), 'static', 'runs', run_id, filename))


@app.route('/projects/')
def project_reports():
    projects = set(x['project'] for x in cli['test_db']['samples'].find(projection={'project': True}))
    return fl.render_template('projects.html', projects=projects)


@app.route('/projects/<project>')
def report_project(project):
    return fl.render_template(
        'project_report.html',

        project=project,
        tab_sets=(
            {
                'name': 'samples',
                'datatables': (
                    {
                        'title': project,
                        'name': project,
                        'api_url': rest_url('samples?where={"project":"%s"}' % project),
                        'cols': col_mappings['samples']
                    },
                )
            },
        )
    )


def _join(*parts):
    return ''.join(parts)


if __name__ == '__main__':

    DEBUG = False

    app.config.from_object(__name__)
    cli = pymongo.MongoClient('localhost', 4998)

    p = argparse.ArgumentParser()
    p.add_argument('-p', '--port', type=int, help='port to run the Flask app on')
    p.add_argument('-r', '--rest-api', type=str, required=True, help='the base url of the REST api to use')
    p.add_argument('-d', '--debug', action='store_true', help='run the app in debug mode')
    p.add_argument(
        '-t',
        '--tornado',
        action='store_true',
        help='use Tornado\'s http server and wsgi container for external access'
    )
    args = p.parse_args()

    rest_api_base = args.rest_api

    if args.tornado:
        import tornado.wsgi
        import tornado.httpserver
        import tornado.ioloop

        http_server = tornado.httpserver.HTTPServer(tornado.wsgi.WSGIContainer(app))
        http_server.listen(args.port)
        tornado.ioloop.IOLoop.instance().start()

    else:
        app.run('localhost', 5000, debug=args.debug)
