'''A collection of strategies for segmenting an image using python and itk.'''


def aniso_gauss_confidence(in_image, out_image, **kwargs):
    '''Perform a segmentation aniso + gauss + confidence connected
    segmentation strategy.'''

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
