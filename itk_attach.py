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


def extract_image_type(img_type):
    '''Awful hack to get around the fact that there's apparently no way to ask
    an itk Image its PixelType'''
    import itk

    type_abbrev = img_type.__name__[img_type.__name__.rfind("Image")+5:-1]
    dim = int(img_type.__name__[-1])

    return (getattr(itk, type_abbrev), dim)


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

    def instantiate(self):
        '''Instantiate an instance of the wrapped class template for use.
        Useful to override in cases where there is unusual templating.'''
        return self.template[self.in_type(), self.out_type()].New()

    def _bind_input(self, instance):
        '''Bind the input of the previous pipeline stage to an instance of the
        class template.'''
        instance.SetInput(self.prev.execute())

    def execute(self):
        '''Execute this and all previous stages recursively to build output
        from this pipeline stage. Returns the result of a GetOutput call to
        the wrapped itk object.'''
        instance = self.instantiate()

        try:
            for param in self.params:
                set_method = getattr(instance, param)
                set_method(self.params[param])
        except TypeError:
            print "Failed to set the parameter", param, "on", type(instance)
            raise

        self._bind_input(instance)
        instance.Update()

        return instance.GetOutput()


class CurvatureFlowPipeStage(PipeStage):
    '''An itk PipeStage that implementsv CurvatureFlowImageFilter.'''

    def __init__(self, previous_stage, iterations, timestep):
        # pylint: disable=no-name-in-module,no-member
        from itk import CurvatureFlowImageFilter

        template = CurvatureFlowImageFilter
        super(CurvatureFlowPipeStage, self).__init__(template,
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
        super(ConfidenceConnectPipeStage, self).__init__(template,
                                                         previous_stage)

        self.params = {"AddSeed": seed,
                       "SetMultiplier": stddevs,
                       "SetNumberOfIterations": iterations,
                       "SetInitialNeighborhoodRadius": neighborhood}

    def out_type(self):
        '''ConfidenceConnectedImageFilter is only able to output as unsigned
        characters.'''
        availiable_out_types = [pair[1] for pair in self.template
                                if pair[0] == self.in_type()]

        if len(availiable_out_types) == 0:
            s = "".join(["ConfidenceConnectPipeStage could not find an",
                         "acceptable output type based upon output type",
                         str(self.in_type()), ". Options were:",
                         str(self.template.GetTypes())])
            raise TypeError(s)

        # temporary hack
        return availiable_out_types[-1]


class FileReader(object):
    '''A PipeStage that can initiate a pipeline using an itk ImageFileReader.
    '''

    def __init__(self, fname, img_type=IMG_F()):
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

    def __init__(self, previous_stage, timestep=0.01, iterations=5,
                 conductance=9.0):
        # pylint: disable=no-name-in-module
        from itk import CurvatureAnisotropicDiffusionImageFilter as templ

        super(AnisoDiffStage, self).__init__(templ, previous_stage)

        self.params = {"SetTimeStep": timestep,
                       "SetNumberOfIterations": iterations,
                       "SetConductanceParameter": conductance}


class GradMagRecGaussStage(PipeStage):
    '''An itk PipeStage that implements
    GradientMagnitudeRecursiveGaussianImageFilter.'''

    def __init__(self, previous_stage, sigma):
        # pylint: disable=no-name-in-module
        from itk import GradientMagnitudeRecursiveGaussianImageFilter as templ

        super(GradMagRecGaussStage, self).__init__(templ, previous_stage)

        self.params = {"SetSigma": sigma}


class SigmoidStage(PipeStage):
    '''An itk PipeStage that implements SigmoidImageFilter. Output min/max
    drawn from ITKExamples SegmentWithGeodesicActiveContourLevelSet.'''

    # pylint: disable=too-many-arguments
    def __init__(self, previous_stage, alpha, beta, out_max=1.0, out_min=0.0):
        # pylint: disable=no-name-in-module,no-member
        from itk import SigmoidImageFilter

        template = SigmoidImageFilter
        super(SigmoidStage, self).__init__(template, previous_stage)

        self.params = {"SetOutputMinimum": out_min,
                       "SetOutputMaximum": out_max,
                       "SetAlpha": alpha,
                       "SetBeta": beta}


class FastMarchingStage(PipeStage):
    '''An itk PipeStage that implements SigmoidImageFilter. It can be run as a
    pure distance calculator with the 'imageless' parameter set to true (an
    input pipe is still required to produce correct output size) or as a true
    image segmentation filter with 'imageless' set to false'''

    def __init__(self, previous_stage, imageless, seeds, seed_value):
        # pylint: disable=no-name-in-module,no-member
        from itk import FastMarchingImageFilter

        template = FastMarchingImageFilter
        super(FastMarchingStage, self).__init__(template, previous_stage)

        self.imageless = imageless

        self.params = {"SetTrialPoints": self.build_seeds(seeds, seed_value),
                       "SetSpeedConstant": 1.0,
                       # "SetStoppingValue": 100
                       }

    def _bind_input(self, instance):
        output = self.prev.execute()

        instance.SetOutputSize(output.GetBufferedRegion().GetSize())
        instance.SetOutputSpacing(output.GetSpacing())

        if not self.imageless:
            instance.SetInput(output)

    def build_seeds(self, seeds, seed_value):
        '''Construct an itk.VectorContainer of itk.LevelSetNode object from
        given input seeds.'''
        # pylint: disable=no-name-in-module,no-member
        from itk import LevelSetNode, VectorContainer, UI

        (px_type, dim) = extract_image_type(self.in_type())
        node_type = LevelSetNode[px_type, dim]

        seed_vect = VectorContainer[UI, node_type].New()
        seed_vect.Initialize()

        for i, seed in enumerate(seeds):
            node = node_type()
            node.SetValue(-seed_value)
            node.SetIndex(seed)
            seed_vect.InsertElement(i, node)

        return seed_vect


class GeoContourLSetStage(PipeStage):
    '''An itk PipeStage that implements a
    GeodesicActiveContourLevelSetImageFilter in the pipestage framework.'''

    def __init__(self, previous_stage, feature_stage, scaling, iterations):
        # pylint: disable=no-name-in-module,no-member
        from itk import GeodesicActiveContourLevelSetImageFilter as Geodesic

        super(GeoContourLSetStage, self).__init__(Geodesic, previous_stage)
        self.prev_feature = feature_stage

        self.params = {"SetPropagationScaling": scaling,
                       "SetNumberOfIterations": iterations,
                       "SetCurvatureScaling": 1.0,
                       "SetAdvectionScaling": 1.0,
                       "SetMaximumRMSError": 0.02}

    def _bind_input(self, instance):
        super(GeoContourLSetStage, self)._bind_input(instance)
        instance.SetFeatureImage(self.prev_feature.execute())

    def instantiate(self):
        img_type = self.in_type()
        feature_type = self.prev_feature.out_type()

        for avail_templ in self.template:
            if avail_templ[0] == img_type and avail_templ[1] == feature_type:
                return self.template[avail_templ].New()

        s = " ".join(["Could not instantiate", str(self.template), "because ",
                      "no valid template combination of", str(img_type), "and",
                      str(feature_type), "could be found. Possibilites were:",
                      str([t for t in self.template])])
        raise TypeError(s)


class BinaryThreshStage(PipeStage):
    '''An itk PipeStage that implements the BinaryThresholdImageFilter.'''

    def __init__(self, previous_stage, output_type=None):
        # pylint: disable=no-name-in-module,no-member
        from itk import BinaryThresholdImageFilter as BinThresh
        from itk import NumericTraits

        super(BinaryThreshStage, self).__init__(BinThresh, previous_stage)

        self.output_type = output_type
        px_type = extract_image_type(self.out_type())[0]

        self.params['SetLowerThreshold'] = -1000.0
        self.params['SetUpperThreshold'] = 0.0
        self.params['SetOutsideValue'] = NumericTraits[px_type].min()
        self.params['SetInsideValue'] = NumericTraits[px_type].max()

    def out_type(self):
        if not self.output_type:
            avail_templ = [t[1] for t in self.template
                           if t[0] == self.in_type()]
            return avail_templ[-1]
        else:
            return self.output_type


class ConverterStage(PipeStage):
    '''An itk PipeStage that implements CastImageFilter to convert from the
    pipeline output type to the specified type.'''

    def __init__(self, previous_stage, type_out):
        # pylint: disable=no-name-in-module
        from itk import CastImageFilter

        super(ConverterStage, self).__init__(CastImageFilter, previous_stage)
        self.type_out = type_out

    def out_type(self):
        return self.type_out
