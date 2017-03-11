Vulkan API is structure-rich, and with good handling of these structures you are going to have good time with the API.

This code demonstrates in python, how to generate code to fill vulkan structures from objects that resemble JSON. The current approach works well for dynamically typed languages and appears to reduce lot of stress about filling up the structures.

The objective is to generate bindings straight from the vulkan specification. These bindings would look like this:

    pInstance = (vk.Instance*1)()
    vk.createInstance(
        vks.InstanceCreateInfo(dict(
            enabledExtensionNames = ["VK_KHR_surface", "VK_KHR_xcb_surface"],
        )),
        None, pInstance)
    instance = pInstance[0]

Automatically generated bindings are relatively maintenance free, so this is a cheap method to generate vulkan support for several different languages.

Ultimately you might want to wrap the objects and create small methods to call Vulkan API. But in practice these bindings are clean enough to use that you could in theory just start prototyping your graphics rendering on top of this.

Clarity provided by dynamic language and clean bindings helps especially beginners to learn a new and a complex API. Additionally they are great help if you intend to experiment and need a short turnaround time.

Here is an another example of what can be done with the results of this project:

    stages = vks.PipelineShaderStageCreateInfo([
        dict(
            stage = {"VERTEX"},
            module = vertex_shader,
            name = "main"),
        dict(
            stage = {"FRAGMENT"},
            module = fragment_shader,
            name = "main")

    vertexInputState = vks.PipelineVertexInputStateCreateInfo(dict(
        vertexBindingDescriptions = [
            dict(binding = 0, stride = 24, inputRate = "VERTEX")
        ],
        vertexAttributeDescriptions = [
            dict(
                binding = 0,
                location = 0,
                format = "R32G32B32_SFLOAT",
                offset = 0),
            dict(
                binding = 0,
                location = 1,
                format = "R32G32B32_SFLOAT",
                offset = 12)
        ]
    ))

    inputAssemblyState = vks.PipelineInputAssemblyStateCreateInfo(dict(
        topology = "TRIANGLE_LIST"
    ))


## Usage

Everything needed to run the script is packed up here. If the spec is outdated, you can obtain the new one from [KhronosGroup/Vulkan-Docs](https://github.com/KhronosGroup/Vulkan-Docs/blob/1.0/src/spec/vk.xml)

To generate bindings with vkstruct, you need my other project chartparser. You can obtain it in http://github.com/cheery/chartparser And you need beautifulsoup4 to parse the `.xml`.

The generated python bindings work as promised, but they are not polished. For serious use they may need lot of work to satisfy every potential case you can come up with. I made them to prototype bindings for http://leverlanguage.com/

The generated json -formatted headers work perfectly in lever programming language. But the Lever is itself varying in quality when it comes to satisfying other peoples needs. Upcoming changes into the FFI layer may require changes into how the API is constructed on the edges such as how the array arguments and function pointers are handled.
