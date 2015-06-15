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
        '''Get the itk type that is input for this pipe stage. Default
        behavior is to draw automatically from the output of the previous
        stage.'''
        return self.prev.out_type()

    def out_type(self):
        '''Get the itk type that is output for this pipe stage. By default the
        behavior is to simply output with the same type as provided for input.
        '''
        return self.in_type()

    def execute(self):
        '''Execute this and all previous stages recursively to build output
        from this pipeline stage. Returns the result of a GetOutput call to
        the wrapped itk object.'''
        instance = self.template[self.in_type(), self.out_type()].New()

        for param in self.params:
            set_method = getattr(instance, param)
            set_method(self.params[param])

        instance.SetInput(self.prev.execute())
        instance.Update()

        return instance.GetOutput()


class CurvatureFlowPipeStage(PipeStage):
    '''An itk PipeStage that implementsv CurvatureFlowImageFilter.'''

    def __init__(self, previous_stage, iterations, timestep):
        # pylint: disable=no-name-in-module,no-member
        from itk import CurvatureFlowImageFilter

        template = CurvatureFlowImageFilter
        super(CurvatureFlowPipeStage, self).__init__(self,
                                                     template,
                                                     previous_stage)

        self.params = {"SetNumberOfIterations": iterations,
                       "SetTimeStep": timestep}


class ConfidenceConnectPipeStage(PipeStage):
    '''An itk PipeStage that implements
    ConfidenceConnectedImageFilter. Default values for parameters
    drawn from ITKExamples SegmentWithGeodesicActiveContourLevelSet.'''

    # pylint: disable=too-many-arguments
    def __init__(self, previous_stage, iterations, stddevs, neighborhood,
                 seed):
        # pylint: disable=no-name-in-module
        from itk import ConfidenceConnectedImageFilter

        template = ConfidenceConnectedImageFilter
        super(ConfidenceConnectPipeStage, self).__init__(self,
                                                         template,
                                                         previous_stage)

        self.params = {"AddSeed": seed,
                       "SetMultiplier": stddevs,
                       "SetNumberOfIterations": iterations,
                       "SetInitialNeighborhoodRadius": neighborhood}


class FileReader(object):
    '''A PipeStage that can initiate a pipeline using an itk ImageFileReader.
    '''

    def __init__(self, fname, img_type):
        self.fname = fname
        self.img_type = img_type

    def out_type(self):
        '''Get type of image read by the wrapped ImageFileReader. This is
        determined based upon user choice at construction.'''
        return self.img_type

    def execute(self):
        '''Execute this pipeline stage--that is, read the image from file and
        build the data into the appropriate itk Image object.'''
        from itk import ImageFileReader  # pylint: disable=no-name-in-module

        reader = ImageFileReader[self.out_type()].New()

        reader.SetFileName(self.fname)

        reader.Update()

        return reader.GetOutput()


class FileWriter(object):
    '''A PipeStage that can close a pipeline by writing to file with an itk
    ImageFileWriter.'''

    def __init__(self, previous_stage, fname):
        self.fname = fname
        self.prev = previous_stage

    def in_type(self):
        '''The type of image provided to the ImageFileWriter by the pipeline.
        '''
        return self.prev.out_type()

    def execute(self):
        '''Execute this pipeline stage--that is, write to file the itk Image
        provided by the input to this pipeline.'''
        from itk import ImageFileWriter  # pylint: disable=no-name-in-module

        writer = ImageFileWriter[self.in_type()].New()
        writer.SetFileName(self.fname)

        writer.SetInput(self.prev.execute())
        writer.Update()


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

        self.params = {"SetTimeStep": timestep,
                       "SetNumberOfIterations": iterations,
                       "SetConductanceParameter": conductance}


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



def attach_converter(pipe, type_in, type_out):
    '''Attach a CastImageFilter to convert from one itk image type to
    another.'''
    # pylint: disable=no-name-in-module
    from itk import CastImageFilter

    conv = CastImageFilter[type_in, type_out].New()

    conv.SetInput(pipe.GetOutput())
    conv.Update()

    return conv
