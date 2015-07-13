import sys
import argparse
import os
import datetime
import json

import sitkstrats


def process_command_line(argv):
    '''Parse the command line and do a first-pass on processing them into a
    format appropriate for the rest of the script.'''

    parser = argparse.ArgumentParser(formatter_class=argparse.
                                     ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        "images", nargs="+",
        help="The dicom directories to operate on.")
    parser.add_argument(
        "--nseeds", type=int, default=10,
        help="The number of randomly placed seeds to produce.")
    parser.add_argument(
        '--media_root', default="media_root/",
        help="The directory to store temporary and intermediate media output")

    args = parser.parse_args(argv[1:])
    args.media_root = os.path.abspath(args.media_root)
    args.images = [os.path.abspath(image) for image in args.images]

    return args


def set_label(fname, label, labsep='-'):
    '''Set the label (a string addition of labsep + label) for this filename.
    '''
    ext = fname[fname.rfind('.'):]
    fname = fname[:fname.rfind('.')]+labsep+label+ext
    return fname


def opthash(options):
    '''Produce a short hash of the input options.'''
    import hashlib

    sha = hashlib.sha1()
    sha.update(str(options))

    return sha.hexdigest()[0:8]


def mediadir_log(func, (in_img, in_opts), mediadir, sha):
    '''Write the input file in the appropriate directory using its sha'''
    optha = opthash(in_opts)
    label = func.__name__

    (img, opts) = func(in_img, in_opts)

    out_fname = os.path.join(mediadir, label, sha+"-"+optha+'.nii')

    sitkstrats.write(img, out_fname)

    opts['file'] = out_fname

    return (img, opts)


def strat_exec(img, sha, seeds, root_dir, indep_strat, dep_strat,
               indep_opts=None, dep_opts=None):
    '''Execute the given strategy with the given options'''
    if indep_opts is None:
        indep_opts = {}
    if dep_opts is None:
        dep_opts = {}

    info = {}

    try:
        optha = opthash(indep_opts)
        seed_indep_img = sitkstrats.read(os.path.join(root_dir,
                                         indep_strat.__name__,
                                         sha + "-" + optha + ".nii"))
        indep_info = indep_opts
        indep_info['file'] = os.path.join(root_dir,
                                          indep_strat.__name__,
                                          sha + "-" + optha + ".nii")
        print "loaded indep_img"
    except RuntimeError:
        print "building "
        (seed_indep_img, indep_info) = mediadir_log(indep_strat,
                                                    (img, indep_opts),
                                                    root_dir, sha)
        print "built in", indep_info['time']

    for seed in seeds:
        seed_name = "-".join([str(k) for k in seed])

        dep_opts = dict(dep_opts)
        dep_opts['seed'] = seed

        # pylint: disable=W0612
        (seed_img, seed_info) = mediadir_log(dep_strat,
                                             (seed_indep_img, dep_opts),
                                             root_dir, sha)

        seed_info['input_file'] = indep_info['file']

        info[seed_name] = {'seed-independent': indep_info,
                           'seed-dependent': seed_info,
                           'seed': seed}

    return info


def run_img(img, sha, nseeds, root_dir):  # pylint: disable=C0111
    '''Run the entire protocol on a particular image starting with sha hash'''
    img_info = {}

    lung_img, lung_info = mediadir_log(sitkstrats.segment_lung,
                                       (img, {}),
                                       root_dir, sha)

    img_info['lungseg'] = lung_info

    segstrat_info = img_info.setdefault('noduleseg', {})

    seeds = sitkstrats.distribute_seeds(lung_img, nseeds)

    # seeds = [(171, 252, 96)]
    # seeds = [(350, 296, 34)]

    connect_dict = strat_exec(
        img, sha, seeds, root_dir,
        indep_strat=sitkstrats.curvature_flow,
        dep_strat=sitkstrats.confidence_connected,
        indep_opts={'curvature_flow': {'timestep': 0.01,
                                       'iterations': 25}},
        dep_opts={'conf_connect': {'iterations': 2,
                                   'multiplier': 1.5,
                                   'neighborhood': 1},
                  'dialate': {'radius': 1}})

    geostrat_dict = strat_exec(
        img, sha, seeds, root_dir,
        indep_strat=sitkstrats.aniso_gauss_sigmo,
        dep_strat=sitkstrats.fastmarch_seeded_geocontour,
        indep_opts={"anisodiff": {'timestep': 0.01,
                                  'conductance': 9.0,
                                  'iterations': 50},
                    "gauss": {'sigma': 1.5},
                    "sigmoid": {'alpha': -20,
                                'beta': 50}},
        dep_opts={"geodesic": {"propagation_scaling": 2.0,
                               "iterations": 300,
                               "curvature_scaling": 1.0,
                               "max_rms_change": 1e-7},
                  "seed_shift": 3})

    waterstrat_dict = strat_exec(
        img, sha, seeds, root_dir,
        indep_strat=sitkstrats.aniso_gauss_watershed,
        dep_strat=sitkstrats.isolate_watershed,
        indep_opts={"anisodiff": {'timestep': 0.01,
                                  'conductance': 9.0,
                                  'iterations': 50},
                    "gauss": {'sigma': 1.5},
                    "watershed": {"level": 4}})

    for seed in seeds:
        seed_name = "-".join([str(s) for s in seed])
        segstrat_info.setdefault(seed_name,
                                 {'geodesic': geostrat_dict[seed_name],
                                  'watershed': waterstrat_dict[seed_name],
                                  'conf_connect': connect_dict[seed_name]})

        seg_files = [strat['seed-dependent']['file']
                     for strat in segstrat_info[seed_name].values()]

        segs = [sitkstrats.read(fname) for fname in seg_files]

        # pylint: disable=W0612
        (consensus, opts) = mediadir_log(
            sitkstrats.segmentation_union,
            (segs, {'threshold': 2.0/3.0,
                    'files': segs}),
            root_dir,
            sha)

        segstrat_info[seed_name]['consensus'] = opts

    return img_info


class DateTimeEncoder(json.JSONEncoder):  # pylint: disable=C0111

    def default(self, obj):  # pylint: disable=E0202
        if isinstance(obj, datetime.datetime):
            return str(obj)
        elif isinstance(obj, datetime.timedelta):
            return str(obj)

        return json.JSONEncoder.default(self, obj)


def main(argv=None):
    '''Run the driver script for this module. This code only runs if we're
    being run as a script. Otherwise, it's silent and just exposes methods.'''
    args = process_command_line(argv)

    run_info = {}

    for img in args.images:
        basename = os.path.basename(img)
        sha = basename[:basename.rfind('.')]

        run_info[sha] = run_img(sitkstrats.read(img), sha,
                                args.nseeds, args.media_root)

    with open("masterseg-run.json", 'w') as f:
        json_out = json.dumps(run_info, sort_keys=True,
                              indent=2, separators=(',', ': '),
                              cls=DateTimeEncoder)
        f.write(json_out)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
