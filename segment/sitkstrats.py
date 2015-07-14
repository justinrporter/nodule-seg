'''A collection of segmentation strategies from sitk instead of itk.'''
import SimpleITK as sitk  # pylint: disable=F0401
import numpy as np
import datetime
import os

import lungseg


def write(img, fname):
    # ImageFileWriter fails if the directory doesn't exist. Create if req'd
    try:
        os.makedirs(os.path.dirname(fname))
    except OSError:
        pass

    out = sitk.ImageFileWriter()
    out.SetFileName(fname)
    out.Execute(img)


def read(fname):
    img_in = sitk.ReadImage(fname)
    img = sitk.Cast(img_in, sitk.sitkFloat32)

    return img


def to_array(img):
    return sitk.GetImageFromArray(img)


def log_size(func):
    '''A decorator that calculates the size of a segmentation.'''
    def exec_func(img, opts=None):
        '''Execute func from outer context and compute the size of the image
        func produces.'''
        if opts is None:
            opts = {}

        (img_out, opts_out) = func(img, opts)

        opts['size'] = np.count_nonzero(  # pylint: disable=E1101
            sitk.GetArrayFromImage(img_out))

        return (img_out, opts_out)

    # If we don't do this, we lose the ability to introspect at higher levels.
    exec_func.__name__ = func.__name__

    return exec_func


def options_log(func):
    '''A decorator that will modify the incoming options object to also include
    information about runtime and algorithm choice.'''
    def exec_func(img, opts=None):
        '''The inner function for options_log'''
        if opts is None:
            opts = {}

        start = datetime.datetime.now()

        (img, out_opts) = func(img, opts)

        out_opts['algorithm'] = func.__name__
        out_opts['time'] = datetime.datetime.now() - start

        return (img, out_opts)

    # If we don't do this, we lose the ability to introspect at higher levels.
    exec_func.__name__ = func.__name__

    return exec_func


def distribute_seeds(img, n_pts=100):
    '''Randomly distribute n seeds amongst all points where img != 0'''
    import random

    array = sitk.GetArrayFromImage(img)

    seeds = list()
    while len(seeds) < n_pts:
        (z, y, x) = [random.randrange(0, i) for i in array.shape]

        if array[z, y, x] != 0 and (z, y, x) not in seeds:
            seeds.append((x, y, z))

    return seeds


def aniso_gauss(img_in, options):
    '''CurvatureAnisotropicDiffusion + GradientMagnitudeRecursiveGaussian is a
    a common featurization strategy. Compute these for consumption by other
    sitkstrat functions.'''

    img = sitk.CurvatureAnisotropicDiffusion(
        img_in,
        timeStep=options['anisodiff']['timestep'],
        conductanceParameter=options['anisodiff']['conductance'],
        # options['anisodiff'].setdefault('scaling_interval', 1),
        numberOfIterations=options['anisodiff']['iterations'])

    img = sitk.GradientMagnitudeRecursiveGaussian(
        img,
        options['gauss']['sigma'])

    return (img, options)


@log_size
@options_log
def segmentation_union(imgs, options):
    '''Compute a consensus segmentation amongst a small set of segmentations'''
    # pylint: disable=E1101
    # Sadly, images and arrays have a different coordinate system (z, y, x) vs
    # (x, y, z) so it's safest just to convert here. Don't worry, it's fast.
    incl_count = np.zeros(sitk.GetArrayFromImage(imgs[0]).shape)
    n_img = 0

    # This would be memory-expensive for large numbers of images, but it's only
    # a couple so ith's hopefully ok.
    for img in [sitk.GetArrayFromImage(i) for i in imgs]:
        assert img.shape == incl_count.shape

        img_size = np.count_nonzero(img)
        if img_size < options['max_size'] and \
           img_size > options['min_size']:
            n_img += 1
            incl_count += (img != 0)

    # store the number of images that passed QC
    options['n_imgs'] = n_img

    if n_img == 0:
        raise RuntimeWarning("No images satisifed image size thresholds" +
                             str((options['min_size'], options['max_size'])))

    # sitk is pretty particular about the datatypes that come in to
    # GetImageFromArray, and the default output from the following (bool?)
    # isn't acceptable apparently
    consensus = np.array(incl_count >= options['threshold'] * n_img,
                         dtype='uint8')

    consensus = sitk.GetImageFromArray(consensus)
    consensus.CopyInformation(imgs[0])
    consensus = sitk.Cast(consensus, sitk.sitkUInt8)

    return (consensus, options)


@log_size
@options_log
def segment_lung(img, options=None):
    '''Produce a lung segmentation from an input image.'''
    if options is None:
        options = {}

    img = lungseg.lungseg(img)

    return (img, options)


@options_log
def curvature_flow(img_in, options):
    img = sitk.CurvatureFlow(
        img_in,
        options['curvature_flow']['timestep'],
        options['curvature_flow']['iterations'])

    return (img, options)


@log_size
@options_log
def confidence_connected(img_in, options):
    img = sitk.ConfidenceConnected(
        img_in,
        [options['seed']],
        options['conf_connect']['iterations'],
        options['conf_connect']['multiplier'],
        options['conf_connect']['neighborhood'])

    img = sitk.BinaryDilate(
        img,
        options['dialate']['radius'],
        sitk.BinaryDilateImageFilter.Ball)

    return (img, options)


@options_log
def aniso_gauss_watershed(img_in, options_in):
    '''Compute CurvatureAnisotropicDiffusion +
    GradientMagnitudeRecursiveGaussian + Sigmoid featurization of the image.'''

    (img, options) = aniso_gauss(img_in, options_in)

    img = sitk.MorphologicalWatershed(
        img,
        level=options['watershed']['level'],
        markWatershedLine=True,
        fullyConnected=False)

    return (img, options)


@log_size
@options_log
def isolate_watershed(img_in, options):
    '''Isolate a particular one of the watershed segmentations.'''
    seed = options['seed']

    arr = sitk.GetArrayFromImage(img_in)

    label = arr[seed[2], seed[1], seed[0]]
    options['label'] = int(label)

    lab_arr = np.array(arr == label, dtype='float32')  # pylint: disable=E1101

    out_img = sitk.GetImageFromArray(lab_arr)
    out_img.CopyInformation(img_in)

    return (out_img, options)


@options_log
def aniso_gauss_sigmo(img_in, opts_in):
    '''Compute CurvatureAnisotropicDiffusion +
    GradientMagnitudeRecursiveGaussian + Sigmoid featurization of the image.'''

    (img, options) = aniso_gauss(img_in, opts_in)

    img = sitk.Sigmoid(
        img,
        options['sigmoid']['alpha'],
        options['sigmoid']['beta'])

    return (img, options)


@log_size
@options_log
def fastmarch_seeded_geocontour(img_in, options):
    '''Segment img_in using a GeodesicActiveContourLevelSetImageFilter with an
    inital level set built using FastMarchingImageFilter at options['seed']'''

    # The speed of wave propagation should be one everywhere, so we produce
    # an appropriately sized np array of all ones and convert it into an img
    ones_img = sitk.GetImageFromArray(np.ones(  # pylint: disable=E1101
        sitk.GetArrayFromImage(img_in).shape))
    ones_img.CopyInformation(img_in)

    fastmarch = sitk.FastMarchingImageFilter()

    # to save time, we limit the distances we calculate to a quarter of the
    # image size away (i.e. a region no more than half the image in diameter).
    fastmarch.SetStoppingValue(max(img_in.GetSize())*0.25)
    seeds = sitk.VectorUIntList()
    seeds.append(options['seed'])
    fastmarch.SetTrialPoints(seeds)

    seed_img = fastmarch.Execute(ones_img)

    # FastMarch won't output the right PixelType, so we have to cast.
    seed_img = sitk.Cast(seed_img, img_in.GetPixelID())

    # Generally speaking, you're supposed to subtract an amount from the
    # input level set, so that growing algorithm doesn't need to go as far
    img_shifted = sitk.GetImageFromArray(
        sitk.GetArrayFromImage(seed_img) - options['seed_shift'])
    img_shifted.CopyInformation(seed_img)
    seed_img = img_shifted

    geodesic = sitk.GeodesicActiveContourLevelSetImageFilter()
    geodesic.SetPropagationScaling(
        options['geodesic']['propagation_scaling'])
    geodesic.SetNumberOfIterations(
        options['geodesic']['iterations'])
    geodesic.SetCurvatureScaling(
        options['geodesic']['curvature_scaling'])
    geodesic.SetMaximumRMSError(
        options['geodesic']['max_rms_change'])

    out = geodesic.Execute(seed_img, img_in)

    options['geodesic']['elapsed_iterations'] = geodesic.GetElapsedIterations()
    options['geodesic']['rms_change'] = geodesic.GetRMSChange()

    out = sitk.BinaryThreshold(out, insideValue=0, outsideValue=1)

    return (out, options)
