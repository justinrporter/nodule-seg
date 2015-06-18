'''A minimal example of the failing behavior of
ShapeDetectionLevelSetImageFilter that I've been observing and can't figure
out. See gist: https://gist.github.com/justinrporter/821e5f38ce56fe7d2954'''

# pylint: disable=all

import itk

internal_type = itk.Image[itk.F, 3]

# output of the anisotropic diffusion-gradient magnitude-sigmoid filter
# pipeline used in many of the segmentation algorithms in the ITK docs
edge_potential = itk.ImageFileReader[internal_type].New()
edge_potential.SetFileName("out-sigmo.nii")
edge_potential.Update()  # req'd so GetSpacing below works

node_type = itk.LevelSetNode[itk.F, 3]  #is there some reason this is not templated on an image type, but rather a CType and an int?
seed_vect = itk.VectorContainer[itk.UI, node_type].New()
seed_vect.Initialize()
node = node_type()
node.SetValue(-10)  # the behavior occurrs for values [-200,200]
node.SetIndex((146, 131, 126))
seed_vect.InsertElement(0, node)

input_level_set = itk.FastMarchingImageFilter[internal_type,
                                              internal_type].New()
input_level_set.SetOutputSize(edge_potential.GetOutput().GetBufferedRegion().GetSize())
input_level_set.SetOutputSpacing(edge_potential.GetOutput().GetSpacing())
input_level_set.SetSpeedConstant(1.0)
input_level_set.SetTrialPoints(seed_vect)

shape_detector = itk.ShapeDetectionLevelSetImageFilter[internal_type,
                                                       internal_type,
                                                       itk.F].New()

shape_detector.SetInput(input_level_set.GetOutput())
shape_detector.SetFeatureImage(edge_potential.GetOutput())
shape_detector.SetPropagationScaling(1.0)
shape_detector.SetCurvatureScaling(10.0)

writer = itk.ImageFileWriter[internal_type].New()
writer.SetInput(shape_detector.GetOutput())
writer.SetFileName("out.nii")
writer.Update()
