import os
import yaml
import datetime
from cached_property import cached_property
from egcg_core.clarity import connection, get_sample
from egcg_core.constants import ELEMENT_REVIEW_COMMENTS, ELEMENT_REVIEW_DATE, ELEMENT_REVIEWED
from eve.methods.patch import patch_internal
from eve.methods.get import get
from werkzeug.exceptions import abort
from config import rest_config
from rest_api import settings
from rest_api.actions.reviews import Action
from rest_api.aggregation.database_side import _aggregate, queries

cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'etc', 'review_thresholds.yaml')
review_thresholds = yaml.safe_load(open(cfg_path, 'r'))


class AutomaticReviewer:
    reviewable_data = None

    @cached_property
    def current_time(self):
        return datetime.datetime.now().strftime(settings.DATE_FORMAT)

    @property
    def cfg(self):
        raise NotImplementedError

    @staticmethod
    def _query(content, parts, ret_default=None):
        top_level = content.copy()
        item = None
        for p in parts:
            item = top_level.get(p)
            if item is None:
                return ret_default
            top_level = item
        return item

    def get_failing_metrics(self):
        passfails = {}

        for metric in self.cfg:
            metric_value = self._query(self.reviewable_data, metric.split('.'))
            comparison = self.cfg[metric]['comparison']
            compare_value = self.cfg[metric]['value']

            check = None
            if metric_value is None:
                check = False

            elif comparison == '>':
                check = metric_value >= compare_value

            elif comparison == '<':
                check = metric_value <= compare_value

            elif comparison == 'agreeswith':
                check = metric_value in (self.reviewable_data[compare_value['key']], compare_value['fallback'])

            passfails[metric] = 'pass' if check else 'fail'

        return sorted(k for k, v in passfails.items() if v == 'fail')

    @property
    def _summary(self):
        failing_metrics = self.get_failing_metrics()
        if failing_metrics:
            return {
                ELEMENT_REVIEWED: 'fail',
                ELEMENT_REVIEW_COMMENTS: 'failed due to ' + ', '.join(
                    [self.cfg.get(f, {}).get('name', f) for f in failing_metrics]),
                ELEMENT_REVIEW_DATE: self.current_time,
            }
        else:
            return {
                ELEMENT_REVIEWED: 'pass',
                ELEMENT_REVIEW_COMMENTS: 'pass',
                ELEMENT_REVIEW_DATE: self.current_time,
            }


class AutomaticLaneReviewer(AutomaticReviewer):
    def __init__(self, aggregated_lane):
        self.reviewable_data = aggregated_lane
        self.run_id = aggregated_lane['run_id']
        self.lane_number = aggregated_lane['lane_number']

    @property
    def cfg(self):
        return review_thresholds['run']

    def push_review(self):
        docs = get('run_elements', run_id=self.run_id, lane=self.lane_number)
        if len(docs[0].get('data')) == 1:
            patch_internal(
                'run_elements',
                payload=self._summary,
                run_id=self.run_id,
                lane=self.lane_number
            )
        else:
            for re in docs[0].get('data'):
                patch_internal(
                    'run_elements',
                    payload=self._summary,
                    run_id=self.run_id,
                    lane=self.lane_number,
                    barcode=re.get('barcode')
                )


class AutomaticRunReviewer(Action):
    def __init__(self, request):
        super().__init__(request)
        self.run_id = self.request.form.get('run_id')

        lanes = _aggregate(
            'run_elements',
            queries.run_elements_group_by_lane,
            request_args={'match': '{"run_id": "%s"}' % self.run_id}
        )
        if not lanes:
            abort(404, 'No data found for run id %s.' % self.run_id)
        self.lane_reviewers = [AutomaticLaneReviewer(lane) for lane in lanes]

    def _perform_action(self):
        for reviewer in self.lane_reviewers:
            reviewer.push_review()
        return {
            'action_id': self.run_id + self.date_started,
            'date_finished': self.now(),
            'action_info': {
                'run_id': self.run_id
            }
        }


class AutomaticSampleReviewer(Action, AutomaticReviewer):
    def __init__(self, request):
        Action.__init__(self, request)
        self.sample_id = self.request.form.get('sample_id')

    @cached_property
    def lims_sample(self):
        connection(new=True, **rest_config.get('clarity'))
        s = get_sample(self.sample_id)
        if not s:
            abort(404, 'Sample %s cannot be found in the Lims' % self.sample_id)
        return s

    @cached_property
    def reviewable_data(self):
        data = _aggregate(
            'samples',
            queries.sample,
            request_args={'match': '{"sample_id": "%s"}' % self.sample_id}
        )
        if data:
            return data[0]
        else:
            abort(404, 'No data found for run id %s.' % self.sample_id)

    @property
    def sample_genotype(self):
        return self.reviewable_data.get('genotype_validation')

    @property
    def species(self):
        return self.reviewable_data.get('species_name')

    def find_value(self, db_key, lims_key):
        value = self.reviewable_data.get(db_key)
        if not value:
            value = self.lims_sample.udf.get(lims_key)
        return value

    @cached_property
    def cfg(self):
        cfg = review_thresholds['sample'].get(self.species, {}).copy()
        cfg.update(review_thresholds['sample']['default'])

        if self.sample_genotype is None:
            cfg.pop('genotype_validation.mismatching_snps', None)
            cfg.pop('genotype_validation.no_call_seq', None)

        required_yield_q30 = self.find_value('required_yield_q30', 'Yield for Quoted Coverage (Gb)')

        if not required_yield_q30:
            abort(404, 'Sample %s does not have a expected yield Q30' % self.sample_id)

        coverage = self.find_value('required_coverage', 'Coverage (X)')
        required_yield = self.find_value('required_yield', 'Required Yield (Gb)')

        if not required_yield:
            abort(404, 'Sample %s does not have a expected yield' % self.sample_id)
        if not coverage:
            abort(404, 'Sample %s does not have a target coverage' % self.sample_id)

        cfg['clean_yield_q30']['value'] = required_yield_q30
        cfg['clean_yield_in_gb']['value'] = required_yield
        cfg['coverage.mean']['value'] = coverage
        return cfg

    @property
    def _summary(self):
        summary = super()._summary
        if self.species == 'Homo sapiens' and self.sample_genotype is None:
            summary[ELEMENT_REVIEWED] = 'genotype missing'
            summary[ELEMENT_REVIEW_COMMENTS] = 'failed due to missing genotype'
        return summary

    def push_review(self):
        patch_internal(
            'samples',
            payload=self._summary,
            sample_id=self.sample_id
        )

    def _perform_action(self):
        self.push_review()
        return {
            'action_id': self.sample_id + self.date_started,
            'date_finished': self.now(),
            'action_info': {
                'sample_id': self.sample_id
            }
        }
