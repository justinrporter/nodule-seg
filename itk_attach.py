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


class PipeStage(object):
    '''A stub itk pipeline stage, to be inherited from by other classes.'''

    def __init__(self, template, previous_stage):
        self.prev = previous_stage
        self.template = template
        self.params = {}

    def in_type(self):
        '''Get the itk type that is input for this pipe stage.'''
        return self.prev.out_type()

    def out_type(self):
        '''Get the itk type that is output for this pipe stage.'''
        return self.in_type()

    def execute(self):
        '''Execute this and all previous stages recursively to build output
        from this pipeline stage.'''
        instance = self.template[self.in_type(), self.out_type()].New()

        for param in self.params:
            method_name = "Set" + param
            set_method = getattr(instance, method_name)

            set_method(self.params[param])

        instance.SetInput(self.prev.GetOutput())
        self.prev.execute()
        instance.Update()


class AnisoDiffStage(PipeStage):
    '''An itk PipeStage that implements
    CurvatureAnisotropicDiffusionImageFilter. Default values for parameters
    drawn from ITKExamples SegmentWithGeodesicActiveContourLevelSet.'''

    def __init__(self, previous_stage, timestep=0.125, iterations=5,
                 conductance=9.0):
        # pylint: disable=no-name-in-module
        from itk import CurvatureAnisotropicDiffusionImageFilter

        template = CurvatureAnisotropicDiffusionImageFilter
        super(AnisoDiffStage, self).__init__(self, template, previous_stage)

        self.params = {"TimeStep": timestep,
                       "NumberOfIterations": iterations,
                       "ConductanceParameter": conductance}


def attach_gradient_mag(pipe, sigma):
    '''Attach a GradientMagnitudeRecursiveGaussianImageFilter to the given
    filter pipeline/stack.'''
    # pylint: disable=no-name-in-module
    from itk import GradientMagnitudeRecursiveGaussianImageFilter

    gmrgif = GradientMagnitudeRecursiveGaussianImageFilter[IMG_F(),
                                                           IMG_F()].New()

    gmrgif.SetInput(pipe.GetOutput())
    gmrgif.SetSigma(sigma)

    gmrgif.Update()

    return gmrgif


def attach_sigmoid(pipe, alpha, beta, out_max=1.0, out_min=0.0):
    '''Attach a SigmoidImageFilter to the output of the given
    filter stack. Output min/max drawn from ITKExamples
    SegmentWithGeodesicActiveContourLevelSet'''
    # pylint: disable=no-name-in-module,no-member
    from itk import SigmoidImageFilter

    sif = SigmoidImageFilter[IMG_F(), IMG_F()].New()

    sif.SetOutputMinimum(out_min)
    sif.SetOutputMaximum(out_max)
    sif.SetAlpha(alpha)
    sif.SetBeta(beta)

    sif.SetInput(pipe.GetOutput())
    sif.Update()

    return sif


def attach_fast_marching(pipe):
    '''Attach a FastMarchingImageFilter to the output of the given
    filter stack.'''
    # pylint: disable=no-name-in-module,no-member
    from itk import FastMarchingImageFilter

    fmif = FastMarchingImageFilter[IMG_F(), IMG_F()].New()

    fmif.SetInput(pipe.GetOutput())
    fmif.Update()

    return fmif


def attach_geodesic(pipe, feature_pipe, prop_scaling, iterations):
    '''Attach a FastMarchingImageFilter to the output of the given
    filter stack. It takes input from two pipes, a feature (binary?) pipe and
    a normal pipe'''
    # pylint: disable=no-name-in-module,no-member
    from itk import GeodesicActiveContourLevelSetImageFilter as GeodesicFilter
    from itk import F as itk_F

    gaclsif = GeodesicFilter[IMG_F(), IMG_F(), itk_F].New()

    gaclsif.SetPropagationScaling(prop_scaling)
    gaclsif.SetCurvatureScaling(1.0)
    gaclsif.SetAdvectionScaling(1.0)
    gaclsif.SetMaximumRMSError(0.02)
    gaclsif.SetNumberOfIterations(iterations)

    gaclsif.SetInput(pipe.GetOutput())
    gaclsif.SetFeatureImage(feature_pipe.GetOutput())

    return gaclsif


def attach_flow_smooth(pipe, iterations, timestep):
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
