import copy
import os
import json
import pymongo
from unittest import TestCase
from time import sleep
from rest_api import app
from config import schema
from config import rest_config as cfg
from tests import Helper
from rest_api.aggregation import database_hooks
from unittest.mock import patch


run_element1 = {
    'run_element_id': '150724_test_1_ATGC', 'run_id': '150724_test', 'project_id': 'a_project',
    'sample_id': 'a_sample', 'lane': 1, 'barcode': 'ATGC', 'library_id': 'a_library',
    'bases_r1': 1500000000, 'bases_r2': 1400000000, 'q30_bases_r1': 1400000000, 'q30_bases_r2': 1300000000,
    'clean_bases_r1': 1300000000, 'clean_bases_r2': 1200000000, 'clean_q30_bases_r1': 1200000000,
    'clean_q30_bases_r2': 1100000000, 'total_reads': 9190, 'passing_filter_reads': 8451,
    'pc_reads_in_lane': 54.0, 'reviewed': 'not reviewed', 'useable': 'yes', 'clean_reads': 1337,
    'lane_pc_optical_dups': 0.1, 'adaptor_bases_removed_r1': 1337, 'adaptor_bases_removed_r2': 1338,
    'mapping_metrics': {
        'bam_file_reads': 8420, 'mapped_reads': 8200, 'duplicate_reads': 1000, 'properly_mapped_reads': 8100,
        'picard_dup_reads': 1010, 'picard_opt_dup_reads': 500, 'picard_est_lib_size': 10000, 'mean_insert_size': 450.2,
        'std_dev_insert_size': 68.4, 'median_insert_size': 432.5, 'median_abs_dev_insert_size': 58.5
    },
    'coverage': {'mean': 2.6}, 'gc_bias': {'slope': 0.01, 'mean_deviation': 0.1}
}

run_element2 = {
    'run_element_id': '150724_test_1_ATGA', 'run_id': '150724_test', 'project_id': 'a_project',
    'sample_id': 'a_sample', 'lane': 1, 'barcode': 'ATGC', 'library_id': 'a_library',
    'bases_r1': 1500000001, 'bases_r2': 1400000001, 'q30_bases_r1': 1400000001, 'q30_bases_r2': 1300000001,
    'clean_bases_r1': 1300000001, 'clean_bases_r2': 1200000001, 'clean_q30_bases_r1': 1200000001,
    'clean_q30_bases_r2': 1100000001, 'total_reads': 9180, 'passing_filter_reads': 8461,
    'pc_reads_in_lane': 54.1, 'reviewed': 'pass', 'useable': 'yes', 'clean_reads': 1338,
    'lane_pc_optical_dups': 0.1, 'adaptor_bases_removed_r1': 1339, 'adaptor_bases_removed_r2': 1340,
    'mapping_metrics': {
        'bam_file_reads': 8620, 'mapped_reads': 8300, 'duplicate_reads': 1100, 'properly_mapped_reads': 8200,
        'picard_dup_reads': 1110, 'picard_opt_dup_reads': 600, 'picard_est_lib_size': 10000, 'mean_insert_size': 450.2,
        'std_dev_insert_size': 68.4, 'median_insert_size': 432.5, 'median_abs_dev_insert_size': 58.5
    },
    'coverage': {'mean': 2.4}, 'gc_bias': {'slope': 0.011, 'mean_deviation': 0.11}
}

unusable_run_element = {
    'run_element_id': '150724_test_1_ATGT', 'run_id': '150724_test', 'project_id': 'a_project',
    'sample_id': 'a_sample', 'lane': 1, 'barcode': 'ATGC', 'library_id': 'a_library',
    'bases_r1': 1500000002, 'bases_r2': 1400000002, 'q30_bases_r1': 1400000002, 'q30_bases_r2': 1300000002,
    'clean_bases_r1': 1300000002, 'clean_bases_r2': 1200000002, 'clean_q30_bases_r1': 1200000002,
    'clean_q30_bases_r2': 1100000002, 'total_reads': 9170, 'passing_filter_reads': 8471,
    'pc_reads_in_lane': 54.2, 'reviewed': 'pass', 'useable': 'no', 'clean_reads': 1339,
    'lane_pc_optical_dups': 0.1, 'adaptor_bases_removed_r1': 1340, 'adaptor_bases_removed_r2': 1341,
    'mapping_metrics': {
        'bam_file_reads': 8621, 'mapped_reads': 8301, 'duplicate_reads': 1101, 'properly_mapped_reads': 8201,
        'picard_dup_reads': 1111, 'picard_opt_dup_reads': 601, 'picard_est_lib_size': 10003, 'mean_insert_size': 300.5,
        'std_dev_insert_size': 68.4, 'median_insert_size': 432.5, 'median_abs_dev_insert_size': 58.5
    },
    'coverage': {'mean': 2.4}, 'gc_bias': {'slope': 0.012, 'mean_deviation': 0.12}
}


class TestDatabaseHooks(TestCase):
    db_path = os.path.join(Helper.assets_dir, 'mongod_metadata')
    patched_auth = None

    @classmethod
    def setUpClass(cls):
        app.testing = True
        cls.client = app.test_client()

        sleep(1)

        # test the connection to the database to make it is running before running the tests
        cli = pymongo.MongoClient(cfg['db_host'], cfg['db_port'], serverSelectionTimeoutMS=100)
        db = cli[cfg['db_name']]
        db['run_elements'].find_one()

        cls.patched_auth = patch('auth.DualAuth.authorized', return_value=True)
        cls.patched_auth.start()

    def setUp(self):
        self.run_elements = [copy.deepcopy(run_element1), copy.deepcopy(run_element2)]

    def tearDown(self):
        for c in schema.content:
            database_hooks.db[c].drop()

    @classmethod
    def tearDownClass(cls):
        cls.patched_auth.stop()

    @staticmethod
    def json(response):
        return json.loads(response.data.decode('utf-8'))['data']

    def get(self, endpoint):
        r = self.client.get('/api/0.1/' + endpoint)
        return json.loads(r.data.decode('utf-8'))['data']

    def post(self, endpoint, data):
        r = self.client.post(
            '/api/0.1/' + endpoint,
            data=json.dumps(data),
            headers={'Content-Type': 'application/json'}
        )
        if not 200 <= r.status_code <= 299:
            raise AssertionError('POST got response %s: %s' % (r.status, r.data))
        return r.data

    def patch(self, endpoint, where, data):
        url = endpoint + '?where=%s' % json.dumps(where)
        entity = self.get(url)[0]
        r = self.client.patch(
            '/api/0.1/%s/%s' % (endpoint, entity['_id']),
            data=json.dumps(data),
            headers={'Content-Type': 'application/json', 'If-Match': entity['_etag']}
        )
        if not 200 <= r.status_code <= 299:
            raise AssertionError('PATCH got response %s: %s' % (r.status, r.data))
        return r.data

    @staticmethod
    def assert_dict_subsets(exp, obs):
        mismatches = {}
        for k, exp_v in exp.items():
            obs_v = obs.get(k)
            if obs_v != exp_v:
                mismatches[k] = {'subset': exp_v, 'superset': obs_v}
        if mismatches:
            raise AssertionError('Mismatches in dict comparison: %s' % mismatches)

    def test_common_aggregation(self):
        self.post('run_elements', self.run_elements)
        self.post(
            'runs',
            {'run_id': '150724_test', 'number_of_lanes': 8, 'run_elements': ['150724_test_1_ATGC', '150724_test_1_ATGA']}
        )

        exp = {
            'bases_r1': 3000000001, 'bases_r2': 2800000001, 'q30_bases_r1': 2800000001, 'q30_bases_r2': 2600000001,
            'clean_bases_r1': 2600000001, 'clean_bases_r2': 2400000001, 'clean_q30_bases_r1': 2400000001,
            'clean_q30_bases_r2': 2200000001, 'total_reads': 18370, 'passing_filter_reads': 16912, 'clean_reads': 2675,
            'pc_pass_filter': 92.06314643440392, 'pc_q30_r1': 93.33333333555555, 'pc_q30_r2': 92.85714285969388,
            'pc_q30': 93.10344827824018, 'yield_in_gb': 5.800000002, 'yield_q30_in_gb': 5.400000002,
            'clean_yield_in_gb': 5.000000002, 'clean_yield_q30_in_gb': 4.600000002, 'clean_pc_q30': 92.0000000032,
            'clean_pc_q30_r1': 92.30769231065089, 'clean_pc_q30_r2': 91.66666667013888,
            'pc_opt_duplicate_reads': 6.455399061032864,
        }
        obs = self.get('runs')[0]
        self.assert_dict_subsets(exp, obs['aggregated'])

        self.post(
            'run_elements',
            {
                'run_element_id': '150724_test_3_ATGC', 'run_id': '150724_test', 'project_id': 'another_project',
                'sample_id': 'a_sample', 'lane': 3, 'barcode': 'ATGC', 'library_id': 'a_library',
                'bases_r1': 1300000001, 'q30_bases_r1': 1200000001, 'clean_bases_r1': 1100000001,
                'clean_q30_bases_r1': 1000000001, 'total_reads': 9180, 'passing_filter_reads': 8461,
                'pc_reads_in_lane': 54.1, 'reviewed': 'fail', 'useable': 'no'
            }
        )
        exp.update(
            {
                'bases_r1': 4300000002, 'q30_bases_r1': 4000000002, 'clean_bases_r1': 3700000002,
                'clean_q30_bases_r1': 3400000002, 'total_reads': 27550, 'passing_filter_reads': 25373,
                'pc_pass_filter': 92.09800362976407, 'pc_q30_r1': 93.02325581719847, 'pc_q30': 92.95774648184883,
                'yield_in_gb': 7.100000003, 'yield_q30_in_gb': 6.600000003, 'clean_yield_in_gb': 6.100000003,
                'clean_yield_q30_in_gb': 5.600000003, 'clean_pc_q30': 91.80327869255576,
                'clean_pc_q30_r1': 91.89189189627466
            }
        )
        obs = self.get('runs')[0]
        self.assert_dict_subsets(exp, obs['aggregated'])

    def test_run_aggregation(self):
        self.post('run_elements', self.run_elements)
        self.post(
            'runs',
            {'run_id': '150724_test', 'number_of_lanes': 8, 'run_elements': ['150724_test_1_ATGC', '150724_test_1_ATGA']}
        )

        exp = {'project_ids': ['a_project'], 'review_statuses': ['not reviewed', 'pass'],
               'useable_statuses': ['yes'], 'pc_adaptor': 0.00009231034479575506}
        self.assert_dict_subsets(exp, self.get('runs')[0]['aggregated'])

        self.post(
            'run_elements',
            {
                'run_element_id': '150724_test_3_ATGC', 'run_id': '150724_test', 'project_id': 'another_project',
                'sample_id': 'a_sample', 'lane': 3, 'barcode': 'ATGC', 'library_id': 'a_library',
                'bases_r1': 1300000001, 'q30_bases_r1': 1200000001, 'clean_bases_r1': 1100000001,
                'clean_q30_bases_r1': 1000000001, 'adaptor_bases_removed_r1': 1341, 'total_reads': 9180,
                'passing_filter_reads': 8461, 'pc_reads_in_lane': 54.1, 'reviewed': 'fail', 'useable': 'no'
            }
        )

        # add an unknown barcode to test filtering
        self.post(
            'run_elements',
            {
                'run_element_id': '150724_test_3_unknown', 'run_id': '150724_test', 'project_id': 'another_project',
                'sample_id': 'a_sample', 'lane': 3, 'barcode': 'unknown', 'library_id': 'a_library',
                'useable': 'not marked'
            }
        )
        exp.update(
            {'project_ids': ['a_project', 'another_project'], 'review_statuses': ['fail', 'not reviewed', 'pass'],
             'useable_statuses': ['no', 'yes'], 'pc_adaptor': 9.429577460804404e-05}
        )
        self.assert_dict_subsets(exp, self.get('runs')[0]['aggregated'])

        proc = {'proc_id': 'run_150724_test_now', 'dataset_type': 'run', 'dataset_name': '150724_test', 'pid': 1337}
        self.post('analysis_driver_procs', proc)
        self.assert_dict_subsets(proc, self.get('runs')[0]['aggregated']['most_recent_proc'])

        self.patch('run_elements', {'run_element_id': '150724_test_3_ATGC'}, {'adaptor_bases_removed_r1': 1441})
        e = self.get('run_elements?where={"run_element_id":"150724_test_3_ATGC"}')[0]
        assert e['adaptor_bases_removed_r1'] == 1441

        exp['pc_adaptor'] = 9.570422531167427e-05
        self.assert_dict_subsets(exp, self.get('runs')[0]['aggregated'])

    def test_lane_aggregation(self):
        self.post('run_elements', self.run_elements)
        self.post(
            'lanes',
            {
                'lane_id': '150724_test_1', 'run_id': '150724_test', 'lane_number': 1,
                'run_elements': ['150724_test_1_ATGC', '150724_test_1_ATGA']
            }
        )

        exp = {
            'cv': 0.0008362189938346116, 'sample_ids': ['a_sample'], 'pc_adaptor': 9.231034479575506e-05,
            'lane_pc_optical_dups': 0.1, 'useable_statuses': ['yes'], 'review_statuses': ['not reviewed', 'pass']
        }
        obs = self.get('lanes')
        self.assert_dict_subsets(exp, obs[0]['aggregated'])

        self.post(
            'run_elements',
            {
                'run_element_id': '150724_test_1_ATGG', 'run_id': '150724_test', 'project_id': 'another_project',
                'sample_id': 'a_sample', 'lane': 1, 'barcode': 'ATGG', 'library_id': 'a_library',
                'bases_r1': 1300000001, 'q30_bases_r1': 1200000001, 'clean_bases_r1': 1100000001,
                'clean_q30_bases_r1': 1000000001, 'adaptor_bases_removed_r1': 1341, 'total_reads': 9180,
                'passing_filter_reads': 8461, 'pc_reads_in_lane': 54.1, 'reviewed': 'fail', 'useable': 'no'
            }
        )
        # add an unknown barcode to test filtering
        self.post(
            'run_elements',
            {
                'run_element_id': '150724_test_3_unknown', 'run_id': '150724_test', 'project_id': 'another_project',
                'sample_id': 'a_sample', 'lane': 3, 'barcode': 'unknown', 'library_id': 'a_library',
                'useable': 'not marked'
            }
        )
        exp.update(
            {'cv': 0.0006826354028175136, 'pc_adaptor': 9.429577460804404e-05, 'useable_statuses': ['no', 'yes'],
             'review_statuses': ['fail', 'not reviewed', 'pass']}
        )
        self.assert_dict_subsets(exp, self.get('lanes')[0]['aggregated'])

        self.patch('run_elements', {'run_element_id': '150724_test_1_ATGG'}, {'passing_filter_reads': 8471})
        exp['cv'] = 0.0011818933932159319
        self.assert_dict_subsets(exp, self.get('lanes')[0]['aggregated'])

    def test_run_element_aggregation(self):
        self.post('run_elements', self.run_elements[0])
        exp = {
            'pc_pass_filter': 91.95865070729053, 'pc_q30_r1': 93.33333333333333, 'pc_q30_r2': 92.85714285714286,
            'pc_q30': 93.10344827586206, 'yield_in_gb': 2.9, 'clean_yield_in_gb': 2.5, 'yield_q30_in_gb': 2.7,
            'clean_yield_q30_in_gb': 2.3, 'clean_pc_q30_r1': 92.3076923076923, 'clean_pc_q30_r2': 91.66666666666666,
            'clean_pc_q30': 92.0, 'pc_duplicate_reads': 11.87648456057007, 'pc_opt_duplicate_reads': 5.938242280285035,
            'pc_mapped_reads': 97.38717339667458,
        }
        self.assert_dict_subsets(exp, self.get('run_elements')[0]['aggregated'])

        self.patch('run_elements', {'run_element_id': '150724_test_1_ATGC'}, {'clean_q30_bases_r1': 1201000000})
        exp.update({'clean_yield_q30_in_gb': 2.301, 'clean_pc_q30_r1': 92.38461538461539, 'clean_pc_q30': 92.04})
        obs = self.get('run_elements')[0]['aggregated']

        self.assert_dict_subsets(exp, obs)

    def test_project_aggregation(self):
        samples = [
            {'sample_id': 'sample_2', 'project_id': 'test', 'reviewed': 'pass', 'delivered': 'no'},
            {'sample_id': 'sample_3', 'project_id': 'test', 'delivered': 'yes'},
            {'sample_id': 'sample_4', 'project_id': 'test', 'reviewed': 'fail', 'delivered': 'yes'},
        ]
        proc = {'proc_id': 'project_test_now', 'dataset_type': 'project', 'dataset_name': 'test'}
        self.post(
            'analysis_driver_procs',
            proc
        )
        self.post('samples', {'sample_id': 'sample_1', 'project_id': 'test'})
        self.post(
            'projects',
            {'project_id': 'test', 'samples': ['sample_1'], 'analysis_driver_procs': ['project_test_now']}
        )

        self.assert_dict_subsets(
            {'samples': ['sample_1'], 'samples_delivered': [], 'samples_reviewed': []},
            self.get('projects')[0]['aggregated']
        )

        self.post('samples', samples)
        self.assert_dict_subsets({
                'samples': ['sample_1', 'sample_2', 'sample_3', 'sample_4'],
                'samples_reviewed': ['sample_2', 'sample_4'],
                'samples_delivered': ['sample_3', 'sample_4']
            },
            self.get('projects')[0]['aggregated']
        )

        # no patching to test here

    def test_sample_aggregation(self):
        self.run_elements.append(copy.deepcopy(unusable_run_element))
        self.post('run_elements', self.run_elements)

        sample = {
            'sample_id': 'a_sample', 'project_id': 'a_project',
            'run_elements': ['150724_test_1_ATGC', '150724_test_1_ATGA'],
            'genotype_validation': {'no_call_chip': 1, 'no_call_seq': 2, 'mismatching_snps': 5},
            'sex_validation': {'called': 'female', 'provided': 'female'}, 'mapped_reads': 1337,
            'properly_mapped_reads': 1336, 'bam_file_reads': 1338, 'duplicate_reads': 100,
            'species_contamination': {'contaminant_unique_mapped': {'Homo sapiens': 501, 'Thingius thingy': 499}},
            'coverage': {'genome_size': 3000000000, 'bases_at_coverage': {'bases_at_5X': 2900000000, 'bases_at_15X': 2000000000}}
        }
        self.post('samples', sample)

        exp = {
            'genotype_match': 'Match', 'sex_match': 'female', 'pc_mapped_reads': 99.9252615844544,
            'pc_properly_mapped_reads': 99.85052316890882, 'pc_duplicate_reads': 7.473841554559043,
            'matching_species': ['Homo sapiens'], 'coverage_at_5X': 96.66666666666667,
            'coverage_at_15X': 66.66666666666666, 'most_recent_proc': None, 'clean_yield_in_gb': 5.000000002,
            'clean_pc_q30_r1': 92.30769231065089, 'clean_pc_q30': 92.0000000032, 'clean_yield_q30_in_gb': 4.600000002,
            'from_run_elements': {
                'useable_run_elements': ['150724_test_1_ATGA', '150724_test_1_ATGC'],
                'mapped_reads': 16500, 'duplicate_reads': 2100, 'bam_file_reads': 17040,
                'pc_mapped_reads': 96.83098591549296, 'picard_opt_dup_reads': 1100,
                'pc_duplicate_reads': 12.323943661971832, 'pc_opt_duplicate_reads': 6.455399061032864,
                'picard_dup_reads': 2120, 'mean_coverage': 5
            },
            'from_all_run_elements': {
                'pc_duplicate_reads': 12.47418261174545,
                'pc_opt_duplicate_reads': 6.628736214488913,
                'picard_opt_dup_reads': 1701,
                'bam_file_reads': 25661,
                'duplicate_reads': 3201,
                'gc_bias': {'mean_deviation': 0.11, 'slope': 0.011},
                'pc_adaptor': 9.235632177538644e-05,
                'mean_insert_size': 400.3,
                'picard_est_lib_size': 10001
            }
        }

        self.assert_dict_subsets(exp, self.get('samples')[0]['aggregated'])

        self.post(
            'run_elements',
            {
                'run_element_id': '150724_test_2_ATGG', 'run_id': '150724_test', 'project_id': 'a_project',
                'sample_id': 'a_sample', 'lane': 2, 'barcode': 'ATGG', 'library_id': 'a_library',
                'bases_r1': 1300000001, 'q30_bases_r1': 1200000001, 'clean_bases_r1': 1100000001,
                'clean_q30_bases_r1': 1000000001, 'adaptor_bases_removed_r1': 1341, 'total_reads': 9180,
                'passing_filter_reads': 8461, 'pc_reads_in_lane': 54.1, 'reviewed': 'fail', 'useable': 'yes',
                'coverage': {'mean': 1.5}
            }
        )

        exp.update(
            {'clean_yield_in_gb': 6.100000003, 'clean_pc_q30_r1': 91.89189189627466,
             'clean_pc_q30': 91.80327869255576, 'clean_yield_q30_in_gb': 5.600000003}
        )
        exp['from_run_elements']['mean_coverage'] = 6.5
        exp['from_run_elements']['useable_run_elements'].append('150724_test_2_ATGG')
        exp['from_all_run_elements']['pc_adaptor'] = 9.375999993436801e-05

        self.assert_dict_subsets(exp, self.get('samples')[0]['aggregated'])

        self.patch('run_elements', {'run_element_id': '150724_test_2_ATGG'}, {'clean_q30_bases_r1': 1200001001})
        exp.update(
            {'clean_pc_q30_r1': 97.29732432578523, 'clean_pc_q30': 95.08198360897607,
             'clean_yield_q30_in_gb': 5.800001003}
        )
        self.assert_dict_subsets(exp, self.get('samples')[0]['aggregated'])

    def test_proc_aggregation(self):
        self.post('runs', {'run_id': '150724_test', 'number_of_lanes': 8})
        assert self.get('runs')[0]['aggregated']['most_recent_proc'] is None

        self.post(
            'analysis_driver_procs',
            {'proc_id': 'run_150724_test', 'dataset_type': 'run', 'dataset_name': '150724_test', 'pid': 1337}
        )

        assert self.get('runs')[0]['aggregated']['most_recent_proc']['pid'] == 1337
        self.patch('analysis_driver_procs', {'proc_id': 'run_150724_test'}, {'pid': 1338})
        assert self.get('runs')[0]['aggregated']['most_recent_proc']['pid'] == 1338

    def test_non_aggregated_endpoint(self):
        self.post(
            'analysis_driver_procs',
            {'proc_id': 'run_150724_test', 'dataset_type': 'run', 'dataset_name': '150724_test', 'pid': 1337}
        )
        self.post(
            'analysis_driver_stages',
            {
                'stage_id': 'run_150724_test_stage_1', 'analysis_driver_proc': 'run_150724_test',
                'stage_name': 'stage_1', 'date_started': '01_01_2017_13:00:00'
            }
        )
