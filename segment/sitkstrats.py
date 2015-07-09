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
    img_in = sitk.Cast(img_in, sitk.sitkFloat32)

    return img_in


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

    return exec_func


def options_log(func):
    '''A decorator that will modify the incoming options object to also include
    information about runtime and algorithm choice.'''
    def exec_func(img, opts=None):
        '''The inner function for options_log'''
        if opts is None:
            opts = {}

        start = datetime.datetime.now()

        (img, opts) = func(img, opts)

        opts['algorithm'] = func.__name__
        opts['time'] = datetime.datetime.now() - start

        return (img, opts)

    return exec_func


@log_size
@options_log
def segment_lung(img, options=None):
    '''Produce a lung segmentation from an input image.'''
    if options is None:
        options = {}

    img = lungseg.lungseg(img)

    return (img, options)


@options_log
def curvature_flow(img_in, options={}):
    img = sitk.CurvatureFlow(
        img_in,
        options.setdefault('timestep', 0.01),
        options.setdefault('iterations', 25))

    return (img, options)


@log_size
@options_log
def confidence_connected(img_in, options):
    img = sitk.ConfidenceConnected(
        img_in,
        [options['seed']],
        options.setdefault('iterations', 2),
        options.setdefault('multiplier', 1.8),
        options.setdefault('neighborhood', 1),
        options.setdefault('replace_value', 1))

    return (img, options)


@options_log
def aniso_gauss_sigmo(img_in, options):
    '''Compute CurvatureAnisotropicDiffusion +
    GradientMagnitudeRecursiveGaussian + Sigmoid featurization of the image.'''

    options['anisodiff'] = options.setdefault('anisodiff', {})

    img = sitk.CurvatureAnisotropicDiffusion(
        img_in,
        options['anisodiff'].setdefault('timestep', 0.01),
        options['anisodiff'].setdefault('conductance', 9.0),
        options['anisodiff'].setdefault('scaling_interval', 1),
        options['anisodiff'].setdefault('iterations', 50))

    img = sitk.GradientMagnitudeRecursiveGaussian(
        img,
        options['gauss']['sigma'])

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
    fastmarch.SetStoppingValue(max(img_in.GetSize())*0.5)
    seeds = sitk.VectorUIntList()
    seeds.append(options['seed'])
    fastmarch.SetTrialPoints(seeds)

    seed_img = fastmarch.Execute(ones_img)

    # FastMarch won't output the right PixelType, so we have to cast.
    seed_img = sitk.Cast(seed_img, img_in.GetPixelID())

    # Generally speaking, you're supposed to subtract an amount from the
    # input level set, so that growing algorithm doesn't need to go as far
    img_shifted = sitk.GetImageFromArray(
        sitk.GetArrayFromImage(seed_img) - options.setdefault('seed_shift', 3))
    img_shifted.CopyInformation(seed_img)
    seed_img = img_shifted

    options.setdefault('geodesic', {})

    geodesic = sitk.GeodesicActiveContourLevelSetImageFilter()
    geodesic.SetPropagationScaling(
        options['geodesic'].setdefault('propagation_scaling', 2.0))
    geodesic.SetNumberOfIterations(
        options['geodesic'].setdefault('iterations', 300))
    geodesic.SetCurvatureScaling(
        options['geodesic'].setdefault('curvature_scaling', 1.0))
    geodesic.SetMaximumRMSError(
        options['geodesic'].setdefault('max_rms_change', .00000001))

    out = geodesic.Execute(seed_img, img_in)

    options['geodesic']['elapsed_iterations'] = geodesic.GetElapsedIterations()
    options['geodesic']['rms_change'] = geodesic.GetRMSChange()

    out = sitk.BinaryThreshold(out, insideValue=0, outsideValue=1)

    return (out, options)
