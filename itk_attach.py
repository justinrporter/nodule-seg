'''A library of itk-attach functions, to be used to build out itk pipelines.'''


def IMG_UC():  # pylint: disable=invalid-name
    '''dynamically load unsigned character 3d image type to preven super long
    loads on import.'''
    from itk import UC, Image  # pylint: disable=no-name-in-module
    return Image[UC, 3]


def IMG_F():  # pylint: disable=invalid-name
    '''dynamically load 3d float image type to preven super long loads when
    on import.'''
    from itk import F, Image  # pylint: disable=no-name-in-module
    return Image[F, 3]


def attach_smooth(pipe, iterations, timestep):
    '''Attach a CurvatureFlowImageFilter to the output of the given
    filter stack.'''
    # pylint: disable=no-name-in-module,no-member
    from itk import CurvatureFlowImageFilter

    cfif = CurvatureFlowImageFilter[IMG_F(), IMG_F()].New()

    cfif.SetNumberOfIterations(iterations)
    cfif.SetTimeStep(timestep)

    cfif.SetInput(pipe.GetOutput())
    cfif.Update()

    return cfif


def attach_converter(pipe, type_in, type_out):
    '''Attach a CastImageFilter to convert from one itk image type to
    another.'''
    # pylint: disable=no-name-in-module
    from itk import CastImageFilter

    conv = CastImageFilter[type_in, type_out].New()

    conv.SetInput(pipe.GetOutput())
    conv.Update()

    return conv


def attach_connect(pipe, iterations, stddevs, neighborhood, seed):
    '''Attach a ConfidenceConnectedImageFilter to the output of the given
    filter stack.'''
    # pylint: disable=no-name-in-module, no-member
    from itk import ConfidenceConnectedImageFilter

    ccif = ConfidenceConnectedImageFilter[IMG_F(), IMG_UC()].New()

    ccif.AddSeed(seed)
    ccif.SetNumberOfIterations(iterations)
    ccif.SetMultiplier(stddevs)
    ccif.SetInitialNeighborhoodRadius(neighborhood)

    ccif.SetInput(pipe.GetOutput())

    ccif.Update()

    return ccif


def get_reader(fname):
    '''Initialize a filter pipeline by building an ImageFileReader based on
    the given file 'fname'.'''
    from itk import ImageFileReader  # pylint: disable=no-name-in-module

    reader = ImageFileReader[IMG_F()].New()

    reader.SetFileName(fname)

    reader.Update()

    return reader


def attach_writer(pipe, fname):
    '''Initialize and attach an ImageFileWriter to the end of a filter pipeline
    to write out the result.'''
    from itk import ImageFileWriter  # pylint: disable=no-name-in-module

    writer = ImageFileWriter[IMG_UC()].New()

    writer.SetInput(pipe.GetOutput())
    writer.SetFileName(fname)

    return writer
