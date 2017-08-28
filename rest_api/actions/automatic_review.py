import os

import datetime
import yaml
from cached_property import cached_property
from egcg_core.constants import ELEMENT_REVIEW_COMMENTS, ELEMENT_REVIEW_DATE, ELEMENT_REVIEWED
from eve.methods.patch import patch_internal
from eve.methods.get import get

from rest_api import settings
from rest_api.aggregation.database_side import _aggregate, queries

cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'etc', 'review_thresholds.yaml')
review_thresholds = yaml.safe_load(open(cfg_path, 'r'))


class Reviewer():
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
                ELEMENT_REVIEW_DATE: self.current_time,
            }


class LaneReviewer(Reviewer):
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


class RunReviewer:
    def __init__(self, run_id):
        self.run_id = run_id
        lanes = _aggregate('run_elements', queries.run_elements_group_by_lane, request_args={'match':'{"run_id": "%s"}' % run_id})
        if not lanes:
            raise ValueError('No data found for run id %s.' % run_id)
        self.lane_reviewers = [LaneReviewer(lane) for lane in lanes]

    @cached_property
    def _summary(self):
        return [r._summary for r in self.lane_reviewers]

    def push_review(self):
        for reviewer in self.lane_reviewers:
            reviewer.push_review()


class SampleReviewer(Reviewer):
    coverage_values = {30: (40, 30), 95: (120, 30), 120: (160, 40), 190: (240, 60), 270: (360, 90)}

    def __init__(self, sample_id):
        self.sample_id = sample_id
        self.reviewable_data = _aggregate(
            'samples',
            queries.sample,
            request_args={'sample_id': sample_id}
        )
        if self.reviewable_data:
            self.reviewable_data = self.reviewable_data[0]
        self.sample_genotype = self.reviewable_data.get('genotype_validation')
        self.species = self.reviewable_data.get('species_name')


    @cached_property
    def cfg(self):
        cfg = review_thresholds['sample'].get(self.species, {}).copy()
        cfg.update(review_thresholds['sample']['default'])

        if self.sample_genotype is None:
            cfg.pop('genotype_validation.mismatching_snps', None)
            cfg.pop('genotype_validation.no_call_seq', None)

        yieldq30 = self.reviewable_data.get(
            'expected_yield_q30'
        )

        expected_yield, coverage = self.coverage_values[yieldq30]
        cfg['clean_yield_q30']['value'] = yieldq30
        cfg['clean_yield_in_gb']['value'] = expected_yield
        cfg['mean_coverage']['value'] = coverage
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
