import logging

from pbsmrtpipe.core import register_pipeline
from pbsmrtpipe.constants import to_pipeline_ns

from .pb_pipelines_sa3 import Constants, Tags, _core_align, _core_gc

log = logging.getLogger(__name__)


def dev_register(relative_id, display_name, tags=()):
    relative_id = 'x_' + relative_id
    display_name = 'x_' + display_name
    pipeline_id = to_pipeline_ns(relative_id)
    ptags = list(set(tags + (Tags.DENOVO, )))
    return register_pipeline(pipeline_id, display_name, "0.1.0", tags=ptags)

def _get_falcon_pipeline(i_cfg, i_fasta_fofn):
    """Basic falcon pipeline components.
    """
    b0 = [
          (i_cfg,        'falcon_ns.tasks.task_falcon_config:0'),
          (i_fasta_fofn, 'falcon_ns.tasks.task_falcon_config:1'),
          ('falcon_ns.tasks.task_falcon_config:0', 'falcon_ns.tasks.task_falcon_make_fofn_abs:0'),
    ]
    bfx = [
          ('falcon_ns.tasks.task_falcon_config:0',        'falcon_ns.tasks.task_falconx:0'),
          ('falcon_ns.tasks.task_falcon_make_fofn_abs:0', 'falcon_ns.tasks.task_falconx:1'),
         ]
    results = dict()
    results['asm'] = 'falcon_ns.tasks.task_falconx:0'
    return b0 + bfx, results

def _get_polished_falcon_pipeline():
    subreadset = Constants.ENTRY_DS_SUBREAD

    btf = [(subreadset, 'pbcoretools.tasks.bam2fasta:0')]
    ftfofn = [('pbcoretools.tasks.bam2fasta:0', 'pbcoretools.tasks.fasta2fofn:0')]

    i_fasta_fofn = 'pbcoretools.tasks.fasta2fofn:0'

    gen_cfg = [(i_fasta_fofn, 'falcon_ns.tasks.task_falcon_gen_config:0')]

    i_cfg = 'falcon_ns.tasks.task_falcon_gen_config:0'

    falcon, falcon_results = _get_falcon_pipeline(i_cfg, i_fasta_fofn)

    ref = falcon_results['asm']

    faidx = [(ref, 'pbcoretools.tasks.fasta2referenceset:0')]

    aln = 'pbalign.tasks.pbalign:0'
    ref = 'pbcoretools.tasks.fasta2referenceset:0'

    polish = _core_align(subreadset, ref) + _core_gc(aln,
                                                     ref)
    results = dict()
    results['aln'] = aln
    results['ref'] = ref

    return ((btf + ftfofn + gen_cfg + falcon + faidx + polish), results)

@dev_register("pipe_falcon_with_fofn", "Falcon FOFN Pipeline",
              tags=("local", "chunking", "internal"))
def get_task_falcon_local_pipeline2():
    """Simple falcon local pipeline.
    Use an entry-point for FASTA input.
    """
    return _get_falcon_pipeline('$entry:e_01', '$entry:e_02')[0]

@dev_register("pipe_falcon", "Falcon Pipeline",
              tags=("local", "chunking", "internal"))
def get_task_falcon_local_pipeline1():
    """Simple falcon local pipeline.
    FASTA input comes from config file.
    """
    i_cfg = '$entry:e_01'
    init = [
          (i_cfg, 'falcon_ns.tasks.task_falcon_config_get_fasta:0'),
           ]
    i_fasta_fofn = 'falcon_ns.tasks.task_falcon_config_get_fasta:0' # output from init
    return init + _get_falcon_pipeline(i_cfg, i_fasta_fofn)[0]

@dev_register("polished_falcon", "Polished Falcon Pipeline",
              tags=("chunking", "internal"))
def get_task_polished_falcon_pipeline():
    """Simple polished falcon local pipeline.
    FASTA input comes from the SubreadSet.
    """
    i_cfg = '$entry:e_01'
    subreadset = Constants.ENTRY_DS_SUBREAD

    btf = [(subreadset, 'pbcoretools.tasks.bam2fasta:0')]
    ftfofn = [('pbcoretools.tasks.bam2fasta:0', 'pbcoretools.tasks.fasta2fofn:0')]

    i_fasta_fofn = 'pbcoretools.tasks.fasta2fofn:0'

    falcon, falcon_results = _get_falcon_pipeline(i_cfg, i_fasta_fofn)

    ref = falcon_results['asm']

    faidx = [(ref, 'pbcoretools.tasks.fasta2referenceset:0')]

    ref = 'pbcoretools.tasks.fasta2referenceset:0'

    polish = _core_align(subreadset, ref) + _core_gc('pbalign.tasks.pbalign:0',
                                                     ref)

    return btf + ftfofn + falcon + faidx + polish

@dev_register("polished_falcon_lean", "Assembly (HGAP 4) without reports", tags=("internal",))
def get_falcon_pipeline_lean():
    """Simple polished falcon local pipeline (sans reports).
    FASTA input comes from the SubreadSet.
    Cfg input is built from preset.xml
    """
    falcon, _ = _get_polished_falcon_pipeline()
    return falcon

@dev_register("polished_falcon_fat", "Assembly (HGAP 4)")
def get_falcon_pipeline_fat():
    """Same as polished_falcon_lean, but with reports.
    """
    falcon, results = _get_polished_falcon_pipeline()

    # id's of results from falcon:
    aln = 'pbalign.tasks.pbalign:0'
    ref = 'pbcoretools.tasks.fasta2referenceset:0'

    # summarize the coverage:
    sum_cov = [(aln, "pbreports.tasks.summarize_coverage:0"),
               (ref, "pbreports.tasks.summarize_coverage:1")]

    # gen polished_assembly report:
    # takes alignment summary GFF, polished assembly fastQ
    polished_report = [('pbreports.tasks.summarize_coverage:0', 'pbreports.tasks.polished_assembly:0'),
                       ('genomic_consensus.tasks.variantcaller:2', 'pbreports.tasks.polished_assembly:1')]

    return falcon + sum_cov + polished_report
