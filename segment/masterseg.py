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

    (img, opts) = func(in_img, in_opts)

    label = opts['algorithm']
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
                                         'aniso_gauss_sigmo', sha + "-" +
                                                      optha + ".nii"))
        indep_info = indep_opts
        indep_info['file'] = os.path.join(root_dir,
                                          'aniso_gauss_sigmo',
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

    print info[seed_name]['seed-dependent']['size'] / 17825792.0
    print info[seed_name]['seed-dependent']['geodesic']['elapsed_iterations']
    print info[seed_name]['seed-dependent']['geodesic']['rms_change']

    return info


def run_img(img, sha, nseeds, root_dir):  # pylint: disable=C0111
    '''Run the entire protocol on a particular image starting with sha hash'''
    img_info = {}

    lung_img, lung_info = mediadir_log(sitkstrats.segment_lung,
                                       (img, {}),
                                       root_dir, sha)

    img_info['lungseg'] = lung_info

    print nseeds
    # seeds = lungseg.get_seeds(lung_img, nseeds)['medpy_indexed']

    # seeds = [(171, 252, 96)]
    seeds = [(350, 296, 34)]

    # img_info['conf_connect'] = strat_exec(
    #     img, sha, seeds, root_dir,
    #     sitkstrats.curvature_flow, sitkstrats.confidence_connected)

    img_info['geodesic'] = strat_exec(
        img, sha, seeds, root_dir,
        indep_strat=sitkstrats.aniso_gauss_sigmo,
        dep_strat=sitkstrats.fastmarch_seeded_geocontour,
        indep_opts={"gauss": {'sigma': 1.5},
                    "sigmoid": {'alpha': -20,
                                'beta': 50}})

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
    being run as a script. Otherwise, it's sislent and just exposes methods.'''
    args = process_command_line(argv)

    run_info = {}

    for img in args.images:
        basename = os.path.basename(img)
        sha = basename[:basename.rfind('.')]

        run_info[sha] = run_img(sitkstrats.read(img), sha,
                                args.nseeds, args.media_root)

    with open("masterseg-run.json", 'w') as f:
        json_out = json.dumps(run_info, sort_keys=True,
                              indent=4, separators=(',', ': '),
                              cls=DateTimeEncoder)
        f.write(json_out)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
