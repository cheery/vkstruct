from ctypes import byref, c_uint32
import vk
import ctypes
import time

ci = vk.InstanceCreateInfo(dict(
    applicationInfo = dict(
        applicationName = "vkstruct test",
        applicationVersion = 1,
        engineName = "hello engine",
        engineVersion = 1,
        apiVersion = (1 << 22 | 0 << 12 | 0)
    ),
    enabledLayerNames = ["VK_LAYER_LUNARG_api_dump"],
    enabledExtensionNames = ["VK_KHR_surface", "VK_KHR_xcb_surface"],
))
instance = vk.Instance()
vk.createInstance(ci, None, instance)

count = c_uint32()
vk.enumeratePhysicalDevices(instance, byref(count), None)
physicaldevices = vk.PhysicalDevice.array(count.value)
vk.enumeratePhysicalDevices(instance, byref(count), physicaldevices)
for dev in physicaldevices:
    prop = vk.PhysicalDeviceProperties.blank()
    vk.getPhysicalDeviceProperties(dev, byref(prop))
    print "apiversion", prop.apiVersion
    print "driversion", prop.driverVersion
    print "vendorid", prop.vendorID
    print "deviceid", prop.deviceID
    print "devicetype", prop.deviceType
    print "devicename", prop.deviceName

    vk.getPhysicalDeviceQueueFamilyProperties(dev, byref(count), None)
    queuefamilies = vk.QueueFamilyProperties.array(count.value)
    vk.getPhysicalDeviceQueueFamilyProperties(dev, byref(count), queuefamilies)

    graphicQueueIndex = -1
    for index, family in enumerate(queuefamilies):
        qf = vk.QueueFlags(family.queueFlags)
        print qf
        if "GRAPHICS_BIT" in qf:
            graphicQueueIndex = index
        #print family.queueCount
        #print family.timestampValidBits
        #print family.minImageTransferGranularity
        #print family.minImageTransferGranularity.width
        #print family.minImageTransferGranularity.height
        #print family.minImageTransferGranularity.depth

    if graphicQueueIndex < 0:
        raise Exception("No fitting queue")
    break
else:
    raise Exception("No devices found")

gpu = dev
ci = vk.DeviceCreateInfo(dict(
    queueCreateInfos = [dict(
        queueFamilyIndex = graphicQueueIndex,
        queuePriorities = [1.0]
    )],
    enabledLayerNames = ["VK_LAYER_LUNARG_api_dump"],
    enabledExtensionNames = ["VK_KHR_swapchain"]
))

dev = vk.Device()
vk.createDevice(gpu, ci, None, dev)

vk.deviceWaitIdle(dev)

queue = vk.Queue()
vk.getDeviceQueue(dev, graphicQueueIndex, 0, queue)

vk.queueWaitIdle(queue)
print "success"

# Now, we do not have anything to draw to, but it's nice to check
# whether the things work or not. Lets create a little part of a structure for creating
# a pipeline, so you can see it works.
begin = time.time()
pipeline = vk.GraphicsPipelineCreateInfo(dict(
    vertexInputState = dict(
        vertexBindingDescriptions = [
            dict(binding = 0, stride = 24, inputRate = "VERTEX"),
        ],
        vertexAttributeDescriptions = [
            dict(binding = 0, location = 0, format = "R32G32B32_SFLOAT", offset = 0),
            dict(binding = 0, location = 1, format = "R32G32B32_SFLOAT", offset = 12),
        ]
    ),
    inputAssemblyState = dict(topology = "TRIANGLE_LIST"),
    viewportState = dict(
        viewports = [
            dict(x=0, y=0, width=200, height=200, minDepth=0.0, maxDepth=1.0)
        ],
        scissors = [
            dict(offset=dict(x=0, y=0), extent=dict(width=200, height=200))
        ]
    )
))
end = time.time()
delta = end - begin
print "took", delta, "seconds"
# True pipeline would be longer than this, but like you can see, it's rather neat.
# Note that it takes ~2ms to fill the structure here, but the pipelines aren't constructed
# in middle of rendering.


vk.destroyDevice(dev, None)
vk.destroyInstance(instance, None)
