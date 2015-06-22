'''A collection of strategies for segmenting an image using python and itk.'''


def aniso_gauss_sigmo_geocontour(in_image, out_image, **kwargs):
    '''Implements a basic strategy that relies upon a gradient magnitude +
    geodesic level set strategy described in the ITK docs.'''

    import itk_attach

    gauss = kwargs['gauss']
    sigmo = kwargs['sigmo']
    geodesic = kwargs['geodesic']

    pipe = itk_attach.FileReader(in_image)
    aniso = itk_attach.AnisoDiffStage(pipe)
    gauss = itk_attach.GradMagRecGaussStage(aniso, gauss['sigma'])
    sigmo = itk_attach.SigmoidStage(gauss, sigmo['alpha'], sigmo['beta'])

    fastmarch = itk_attach.FastMarchingStage(
        pipe,
        imageless=True,
        seeds=kwargs['seed'],
        seed_value=kwargs['seed_distance'])

    pipe = itk_attach.GeoContourLSetStage(
        fastmarch,
        sigmo,
        geodesic['propagation_scaling'],
        geodesic['iterations'])

    if kwargs.get('intermediate_images', False):
        itk_attach.FileWriter(aniso, 'out-aniso.nii').execute()
        itk_attach.FileWriter(gauss, 'out-gauss.nii').execute()
        itk_attach.FileWriter(sigmo, 'out-sigmo.nii').execute()
        itk_attach.FileWriter(fastmarch, 'out-march.nii').execute()

        print "Elapsed Iterations:", pipe.instance.GetElapsedIterations()

    # pipe = itk_attach.BinaryThreshStage(pipe)

    pipe = itk_attach.FileWriter(pipe, out_image)

    # run the pipeline
    pipe.execute()


def aniso_gauss_confidence(in_image, out_image, **kwargs):
    '''Perform an aniso + gauss + confidence connected segmentation strategy.
    '''

    import itk_attach

    smooth_param = kwargs['smooth']
    gauss_param = kwargs['gauss']
    connect_param = kwargs['connect']
    intermediate_images = kwargs.get('intermediate_images', False)

    pipe = itk_attach.FileReader(in_image)

    pipe = itk_attach.AnisoDiffStage(pipe,
                                     smooth_param['timestep'],
                                     smooth_param['iterations'])
    if intermediate_images:
        itk_attach.FileWriter(pipe, "aniso.nii").execute()

    pipe = itk_attach.GradMagRecGaussStage(pipe, gauss_param['sigma'])
    if intermediate_images:
        itk_attach.FileWriter(pipe, "gauss.nii").execute()

    pipe = itk_attach.ConfidenceConnectStage(pipe,
                                             connect_param['seeds'],
                                             connect_param['iterations'],
                                             connect_param['stddevs'],
                                             connect_param['neighborhood'])

    pipe = itk_attach.FileWriter(pipe, out_image)

    pipe.execute()


def flow_confidence(in_image, out_image, **kwargs):
    '''Perform a curvatureflow + confidence connected segmentation strategy.'''

    import itk_attach

    smooth = kwargs['smooth']
    connect = kwargs['connect']
    intermed_img = kwargs.get('intermediate_images', False)

    pipe = itk_attach.FileReader(in_image)

    pipe = itk_attach.CurvatureFlowStage(pipe, smooth['timestep'],
                                         smooth['iterations'])

    if intermed_img:
        itk_attach.FileWriter(pipe, 'curvature.nii').execute()

    pipe = itk_attach.ConfidenceConnectStage(pipe, connect['seeds'],
                                             connect['iterations'],
                                             connect['stddevs'],
                                             connect['neighborhood'])

    if intermed_img:
        itk_attach.FileWriter(pipe, "confidence.nii").execute()

    binary = kwargs.get('binary', None)
    if binary:
        pipe = itk_attach.VotingIterativeBinaryFillholeStage(
            pipe,
            binary['threshold'],
            binary['iterations'])

        if intermed_img:
            itk_attach.FileWriter(pipe, "binvote.nii").execute()

    pipe = itk_attach.BinaryFillholeStage(pipe)

    pipe = itk_attach.FileWriter(pipe, out_image)

    pipe.execute()
