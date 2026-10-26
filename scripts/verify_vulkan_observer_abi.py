#!/usr/bin/env python3
"""Compare observer declarations with actual fetched Vulkan headers before driver build."""
import argparse, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PAIRS={
 'tl_pi_stage':'VkPipelineShaderStageCreateInfo','tl_pi_graphics':'VkGraphicsPipelineCreateInfo','tl_pi_compute':'VkComputePipelineCreateInfo',
 'tl_pi_specialization':'VkSpecializationInfo','tl_pi_map':'VkSpecializationMapEntry','tl_pi_module_ci':'VkShaderModuleCreateInfo',
 'pi_dynamic':'VkPipelineDynamicStateCreateInfo','pi_vertex':'VkPipelineVertexInputStateCreateInfo','pi_assembly':'VkPipelineInputAssemblyStateCreateInfo',
 'pi_tess':'VkPipelineTessellationStateCreateInfo','pi_raster':'VkPipelineRasterizationStateCreateInfo','pi_multi':'VkPipelineMultisampleStateCreateInfo',
 'pi_depth':'VkPipelineDepthStencilStateCreateInfo','pi_blend':'VkPipelineColorBlendStateCreateInfo','pi_viewport':'VkPipelineViewportStateCreateInfo',
 'pi_sampler':'VkSamplerCreateInfo','pi_binding':'VkDescriptorSetLayoutBinding','pi_descriptor_layout':'VkDescriptorSetLayoutCreateInfo',
 'pi_push':'VkPushConstantRange','pi_pipeline_layout':'VkPipelineLayoutCreateInfo','pi_attachment_ref':'VkAttachmentReference',
 'pi_subpass':'VkSubpassDescription','pi_render_pass':'VkRenderPassCreateInfo','pi_rendering':'VkPipelineRenderingCreateInfo'}
# Every renamed field used to dereference a pointer or select array state.
FIELDS={
 'tl_pi_stage':{'next':'pNext','module':'module','name':'pName','specialization':'pSpecializationInfo'},
 'tl_pi_graphics':{'stages':'pStages','vertex':'pVertexInputState','assembly':'pInputAssemblyState','tessellation':'pTessellationState','viewport':'pViewportState','raster':'pRasterizationState','multisample':'pMultisampleState','depth':'pDepthStencilState','blend':'pColorBlendState','dynamic':'pDynamicState','layout':'layout','renderpass':'renderPass','subpass':'subpass','base':'basePipelineHandle','base_index':'basePipelineIndex'},
 'tl_pi_compute':{'stage':'stage','layout':'layout','base':'basePipelineHandle','base_index':'basePipelineIndex'},
 'tl_pi_specialization':{'entries':'pMapEntries','size':'dataSize','data':'pData'},'tl_pi_map':{'id':'constantID','offset':'offset','size':'size'},
 'tl_pi_module_ci':{'size':'codeSize','code':'pCode'},'pi_dynamic':{'states':'pDynamicStates'},
 'pi_vertex':{'bindings':'vertexBindingDescriptionCount','binding_data':'pVertexBindingDescriptions','attributes':'vertexAttributeDescriptionCount','attribute_data':'pVertexAttributeDescriptions'},
 'pi_raster':{'constant':'depthBiasConstantFactor','line':'lineWidth'},'pi_multi':{'mask':'pSampleMask','coverage':'alphaToCoverageEnable'},
 'pi_depth':{'front':'front','back':'back','minimum':'minDepthBounds'},'pi_blend':{'attachments':'pAttachments','constants':'blendConstants'},
 'pi_viewport':{'viewport_data':'pViewports','scissor_data':'pScissors'},'pi_binding':{'samplers':'pImmutableSamplers'},
 'pi_sampler':{'bias':'mipLodBias','anisotropy':'anisotropyEnable','max_anisotropy':'maxAnisotropy','unnormalized':'unnormalizedCoordinates'},
 'pi_descriptor_layout':{'bindings':'pBindings'},'pi_pipeline_layout':{'sets':'setLayoutCount','layouts':'pSetLayouts','pushes':'pushConstantRangeCount','ranges':'pPushConstantRanges'},
 'pi_subpass':{'input':'pInputAttachments','color':'pColorAttachments','resolve':'pResolveAttachments','depth':'pDepthStencilAttachment','preserve':'pPreserveAttachments'},
 'pi_render_pass':{'attachment_data':'pAttachments','subpass_data':'pSubpasses','dependency_data':'pDependencies'},
 'pi_rendering':{'view_mask':'viewMask','formats':'pColorAttachmentFormats','depth':'depthAttachmentFormat','stencil':'stencilAttachmentFormat'}}
def main():
 p=argparse.ArgumentParser();p.add_argument('driver_source',type=Path);p.add_argument('--ios',action='store_true');a=p.parse_args()
 headers=list(a.driver_source.glob('External/**/vulkan/vulkan_core.h'))
 if len(headers)!=1:raise SystemExit(f'Expected exactly one fetched Vulkan SDK, found {len(headers)}')
 include=headers[0].parent.parent
 source='#include <vulkan/vulkan_core.h>\n#include "husk-tl-pipeline-diagnostics.c"\n'
 for local,actual in PAIRS.items():
  source+=f'_Static_assert(sizeof({local})==sizeof({actual}),"size {local}");\n'
  for ours,theirs in FIELDS.get(local,{}).items():source+=f'_Static_assert(offsetof({local},{ours})==offsetof({actual},{theirs}),"offset {local}.{ours}");\n'
 with tempfile.TemporaryDirectory() as d:
  f=Path(d)/'observer_abi.c';f.write_text(source)
  command=['cc','-std=c11','-Wall','-Werror','-fsyntax-only','-I',str(include),'-I',str(ROOT/'src/translation-layer-next'),str(f)]
  if a.ios:
   sdk=subprocess.check_output(['xcrun','--sdk','iphoneos','--show-sdk-path'],text=True).strip()
   command=['xcrun','--sdk','iphoneos','clang','-target','arm64-apple-ios15.5','-isysroot',sdk]+command[1:]
  subprocess.run(command,check=True)
 print(f'M2 actual Vulkan SDK observer ABI: {len(PAIRS)} structures / {sum(map(len,FIELDS.values()))} field offsets passed')
if __name__=='__main__':main()
