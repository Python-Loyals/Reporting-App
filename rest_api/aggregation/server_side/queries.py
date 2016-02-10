__author__ = 'mwham'
from .expressions import *

aggregate_run_element = {
    'pc_pass_filter': Percentage('passing_filter_reads', 'total_reads'),
    'pc_q30_r1': Percentage('q30_bases_r1', 'bases_r1'),
    'pc_q30_r2': Percentage('q30_bases_r2', 'bases_r2'),
    'pc_q30': Percentage(Add('q30_bases_r1', 'q30_bases_r2'), Add('bases_r1', 'bases_r2')),
    'yield_in_gb': Divide(Add('bases_r1', 'bases_r2'), Constant(1000000000))
}

aggregate_sample = {
    'pc_pass_filter': Percentage('passing_filter_reads', 'total_reads'),
    'clean_pc_q30_r1': Percentage('clean_q30_bases_r1', 'clean_bases_r1'),
    'clean_pc_q30_r2': Percentage('clean_q30_bases_r2', 'clean_bases_r2'),
    'clean_pc_q30': Percentage(Add('clean_q30_bases_r1', 'clean_q30_bases_r2'), Add('clean_bases_r1', 'clean_bases_r2')),
    'clean_yield_in_gb': Divide(Add('clean_bases_r1', 'clean_bases_r2'), Constant(1000000000)),
    'clean_yield_q30': Divide(Add('clean_q30_bases_r1', 'clean_q30_bases_r2'), Constant(1000000000)),
    'pc_mapped_reads': Percentage('mapped_reads', 'bam_file_reads'),
    'pc_properly_mapped_reads': Percentage('properly_mapped_reads', 'bam_file_reads'),
    'pc_duplicate_reads': Percentage('duplicate_reads', 'bam_file_reads')
}

aggregate_lane = {
    'pc_q30_r1': Percentage('q30_bases_r1', 'bases_r1'),
    'pc_q30_r2': Percentage('q30_bases_r2', 'bases_r2'),
    'pc_q30': Percentage(Add('q30_bases_r1', 'q30_bases_r2'), Add('bases_r1', 'bases_r2')),
    'pc_pass_filter': Percentage('passing_filter_reads', 'total_reads'),
    'yield_in_gb': Divide(Add('bases_r1', 'bases_r2'), Constant(1000000000)),
    'cv': CoefficientOfVariation('passing_filter_reads')
}

aggregate_run = {
    'pc_q30_r1': Percentage('q30_bases_r1', 'bases_r1'),
    'pc_q30_r2': Percentage('q30_bases_r2', 'bases_r2'),
    'pc_q30': Percentage(Add('q30_bases_r1', 'q30_bases_r2'), Add('bases_r1', 'bases_r2')),
    # 'pc_pass_filter': Percentage('passing_filter_reads', 'total_reads'),
    'project_ids': Concatenate('project_id'),
    'yield_in_gb': Divide(Add('bases_r1', 'bases_r2'), Constant(1000000000)),
    'yield_q30_in_gb': Divide(Add('q30_bases_r1', 'q30_bases_r2'), Constant(1000000000)),
    'clean_yield_in_gb': Divide(Add('clean_bases_r1', 'clean_bases_r2'), Constant(1000000000)),
    'clean_yield_q30_in_gb': Divide(Add('clean_q30_bases_r1', 'clean_q30_bases_r2'), Constant(1000000000))
}

aggregate_project = {
    'nb_samples': NbUniqueElements('samples')
}

aggregate_embedded_run_elements = {  # multi-element
    'bases_r1': Total('bases_r1'),
    'bases_r2': Total('bases_r2'),
    'q30_bases_r1': Total('q30_bases_r1'),
    'q30_bases_r2': Total('q30_bases_r2'),
    'clean_bases_r1': Total('clean_bases_r1'),
    'clean_bases_r2': Total('clean_bases_r2'),
    'clean_q30_bases_r1': Total('clean_q30_bases_r1'),
    'clean_q30_bases_r2': Total('clean_q30_bases_r2'),
    'total_reads': Total('total_reads'),
    'passing_filter_reads': Total('passing_filter_reads'),
    'clean_reads': Total('clean_reads'),
    'run_ids': Concatenate('run_id')
    # 'project_ids': Concatenate('project_id')
}
