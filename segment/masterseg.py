import sys
import argparse
import os
import datetime
import json
import logging

import SimpleITK as sitk
import numpy as np

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
    parser.add_argument(
        '--profile', default=False, action='store_true',
        help="Run cProfile on script execution.")
    parser.add_argument(
        '--log', default="logs/",
        help="The directory to place logs in.")

    args = parser.parse_args(argv[1:])
    args.media_root = os.path.abspath(args.media_root)
    args.images = [os.path.abspath(image) for image in args.images]

    logname = os.path.join(os.path.abspath(args.log),
                           "log-"+str(datetime.datetime.now())+".log")
    logname = "_".join(logname.split())

    logging.basicConfig(filename=logname,
                        level=logging.DEBUG,
                        format='%(asctime)s %(message)s')
    args.log = logname

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


def mediadir_log(func, (in_img, in_opts), mediadir, sha, subdir=None):
    '''Write the input file in the appropriate directory using its sha'''
    optha = opthash(in_opts)
    label = func.__name__

    (img, opts) = func(in_img, in_opts)

    if subdir is None:
        subdir = label

    out_fname = os.path.join(mediadir, subdir, sha+"-"+optha+'.nii')

    sitkstrats.write(img, out_fname)

    opts['file'] = out_fname

    return (img, opts)


def configure_strats():
    '''
    Construct a dictionary that represents the configuration of all
    segmentation strategies to be used in the script using command line
    arguments. CURRENTLY ACCEPTS NO INPUT.
    '''

    strats = {
        'confidence_connected': {
            'seed-independent': {
                'strategy': sitkstrats.curvature_flow,
                'opts': {'curvature_flow': {
                            'timestep': 0.01,
                            'iterations': 25}}
                },
            'seed-dependent': {
                'strategy': sitkstrats.confidence_connected,
                'opts': {'conf_connect': {'iterations': 2,
                                          'multiplier': 1.5,
                                          'neighborhood': 1},
                         'dialate': {'radius': 1}}
                },
        },
        'geodesic': {
            'seed-independent': {
                'strategy': sitkstrats.aniso_gauss_sigmo,
                'opts': {"anisodiff": {'timestep': 0.01,
                                       'conductance': 9.0,
                                       'iterations': 50},
                         "gauss": {'sigma': 1.5},
                         "sigmoid": {'alpha': -20,
                                     'beta': 50}},
            },
            'seed-dependent': {
                'strategy': sitkstrats.fastmarch_seeded_geocontour,
                'opts': {"geodesic": {"propagation_scaling": 2.0,
                                      "iterations": 300,
                                      "curvature_scaling": 1.0,
                                      "max_rms_change": 1e-7},
                         "seed_shift": 3}
            }
        },
        'watershed': {
            'seed-independent': {
                'strategy': sitkstrats.aniso_gauss_watershed,
                'opts': {"anisodiff": {'timestep': 0.01,
                                       'conductance': 9.0,
                                       'iterations': 50},
                         "gauss": {'sigma': 1.5},
                         "watershed": {"level": 20}}
            },
            'seed-dependent': {
                'strategy': sitkstrats.isolate_watershed,
                'opts': {}
            }
        }
    }

    return strats


def seeddep(imgs, seeds, root_dir, sha, segstrats, lung_size):

    # pick an image, basically at random, from imgs to initialize an array
    # that tracks which areas of the image have already been segmented out
    segmented = np.zeros(sitk.GetArrayFromImage(  # pylint: disable=E1101
        imgs.values()[0]).shape)

    out_info = {}

    for seed in seeds:
        try:
            if segmented[seed[2], seed[1], seed[0]] >= 2:
                logging.info(
                    "Tried to segment %s but it was already segmented", seed)
                continue
        except IndexError as err:
            logging.error(" ".join([str(seed), str(segmented.shape)]))
            logging.error(str(err))
            raise err

        # We want to hold onto images and info dicts for each segmentation,
        # and we want to automagically store the info we put in seed_info into
        # out_info for returning later => use setdefault
        out_imgs = {}
        seed_info = out_info.setdefault("-".join([str(k) for k in seed]), {})

        # for each strategy we want to segment with, get its name and the
        # function that executes it.
        for (sname, strat) in [(strnam, segstrats[strnam]['seed-dependent'])
                               for strnam in segstrats]:

            img_in = imgs[sname]

            opts = dict(strat['opts'])
            opts['seed'] = seed

            (tmp_img, tmp_info) = mediadir_log(strat['strategy'],
                                               (img_in, opts),
                                               root_dir,
                                               sha)

            out_imgs[sname] = tmp_img
            seed_info[sname] = tmp_info

            logging.info("Segmented %s with %s", seed, sname)


        # we need the names of the input files so that our options hash is
        # dependent on the input images.
        consensus_input_files = [s['file'] for s in seed_info.values()]

        try:
            (consensus, consensus_info) = mediadir_log(
                sitkstrats.segmentation_union,
                (out_imgs.values(),
                 {'threshold': 2.0/3.0,
                  'max_size': lung_size * 0.5,
                  'min_size': lung_size * 1e-5,
                  'input_files': consensus_input_files}),
                root_dir,
                sha)
        except RuntimeWarning as war:
            logging.info("Failed %s during consensus: %s", seed, war)
            seed_info['consensus'] = "failure"
            continue

        logging.info("Finished segmenting %s", seed)

        segmented += sitk.GetArrayFromImage(consensus)

        seed_info['consensus'] = consensus_info

    return out_info


def run_img(img_in, sha, nseeds, root_dir):  # pylint: disable=C0111
    '''Run the entire protocol on a particular image starting with sha hash'''
    img_info = {}

    lung_img, lung_info = mediadir_log(sitkstrats.segment_lung,
                                       (img_in, {}),
                                       root_dir, sha)
    img_info['lungseg'] = lung_info

    (img, tmp_info) = mediadir_log(sitkstrats.crop_to_segmentation,
                                   (img_in, lung_img),
                                   root_dir, sha, subdir="crop")
    lung_img = sitkstrats.crop_to_segmentation(lung_img, lung_img)[0]
    img_info['crop'] = tmp_info

    segstrats = configure_strats()
    seed_indep_imgs = {}
    seed_indep_info = {}

    for (sname, strat) in [(strnam, segstrats[strnam]['seed-independent'])
                           for strnam in segstrats]:

        try:
            optha = opthash(strat['opts'])
            fname = os.path.join(root_dir, strat['strategy'].__name__,
                                 sha + "-" + optha + ".nii")
            tmp_img = sitkstrats.read(fname)
            tmp_info = strat['opts']
            tmp_info['file'] = os.path.join(fname)
            logging.info(
                "Loaded seed-independent image for '%s', '%s' from file",
                sname, fname)
        except RuntimeError:
            logging.debug(
                "Building seed-independent image '%s', '%s'.", sname, fname)
            (tmp_img, tmp_info) = mediadir_log(strat['strategy'],
                                               (img, strat['opts']),
                                               root_dir,
                                               sha)
            logging.info(
                "Built seed-independent image '%s', '%s' in %s",
                sname, fname, tmp_info['time'])

        seed_indep_imgs[sname] = tmp_img
        seed_indep_info[sname] = tmp_info

    # compute seeds, first by taking the centers of mass of a bunch of the
    # watershed segemented regions, then by adding a bunch of random ones that
    # are inside the lung field.
    (seeds, tmp_info) = sitkstrats.com_calc(img=seed_indep_imgs['watershed'],
                                            max_size=0.05, min_size=1e-5,
                                            lung_img=lung_img)
    img_info['deterministic-seeds'] = tmp_info
    seeds.extend(sitkstrats.distribute_seeds(lung_img, nseeds-len(seeds)))

    # with many deterministic seeds, this list can be longer than nseeds.
    seeds = seeds[0:nseeds]

    seg_info = seeddep(seed_indep_imgs, seeds,
                       root_dir, sha, segstrats, img_info['lungseg']['size'])

    img_info['noduleseg'] = {}
    for seed in seg_info:
        for segstrat in seg_info[seed]:
            combined_info = {'seed-dependent': seg_info[seed][segstrat]}

            if segstrat in seed_indep_info:
                combined_info['seed-independent'] = seed_indep_info[segstrat]

            img_info['noduleseg'].setdefault(
                seed, {})[segstrat] = combined_info

    return img_info


class DateTimeEncoder(json.JSONEncoder):  # pylint: disable=C0111

    def default(self, obj):  # pylint: disable=E0202
        if isinstance(obj, datetime.datetime):
            return str(obj)
        elif isinstance(obj, datetime.timedelta):
            return str(obj)

        return json.JSONEncoder.default(self, obj)


def write_info(info, filename="masterseg-run.json"):
    with open(filename, 'w') as f:
        try:
            json_out = json.dumps(info, sort_keys=True,
                                  indent=2, separators=(',', ': '),
                                  cls=DateTimeEncoder)
        except TypeError as err:
            logging.error("Error encountered serializing for JSON, dumping " +
                          "dict here:\n"+str(info))
            raise err

        f.write(json_out)


def main(argv=None):
    '''Run the driver script for this module. This code only runs if we're
    being run as a script. Otherwise, it's silent and just exposes methods.'''
    args = process_command_line(argv)

    run_info = {}
    for img in args.images:
        basename = os.path.basename(img)
        sha = basename[:basename.rfind('.')]

        logging.info("Beginning image %s", img)

        run_info[sha] = run_img(sitkstrats.read(img), sha,
                                args.nseeds, args.media_root)

    write_info(run_info)

    return 1


if __name__ == "__main__":
    if "--profile" in sys.argv:
        import cProfile
        sys.exit(cProfile.runctx("main(sys.argv)", globals(),
                                 {"sys.argv": sys.argv}))
    else:
        sys.exit(main(sys.argv))
