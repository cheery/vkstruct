from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, Tag
import json, re, os
import vkparser

vk_xml = "./spec/vk.xml"
vk_json = "libvulkan.json"

typemap = {
    "VkSampleMask": "u32",
    "VkBool32":     "u32",
    "VkDeviceSize": "u64",
}

def translate():
    libvulkan = {}
    libvulkan["comment"] = [
        "This file was automatically generated by vkstruct_json.py",
        "You may want to edit the generator rather than this file."]

    with open(vk_xml) as fd:
        soup = BeautifulSoup(fd.read(), 'xml')
    registry = soup.registry

    libvulkan["constants"] = constants = {}
    libvulkan["types"] = types = {}

    enumerations = set()
    for tag in registry:
        if tag.name == "enums":
            if tag.get("name") == "API Constants":
                constants.update(translate_api_constants(tag))
                continue
            if tag.get("type") == "enum":
                translate_enumeration(types, tag, "enum")
                continue
            if tag.get("type") == "bitmask":
                translate_enumeration(types, tag, "bitmask")
                continue
            assert False, tag
    
    for tag in registry.types:
        if tag.name == "type":
            category = tag.get("category")
            if category == "include":
                continue
            if category == "define":
                continue
            if category == "basetype":
                continue
            if category == "bitmask":
                name = tag.find("name").text
                name = rename_enumeration(name)
                if name not in types and name:
                    types[name] = "i32"
                continue
            if category == "handle":
                translate_handle(types, tag)
                continue
            if category == "enum":
                name = tag["name"]
                name = rename_enumeration(name)
                if name not in types and name:
                    types[name] = "i32"
                continue
            if category == "funcpointer":
                translate_funcpointer(types, constants, tag)
                continue
            if category == "struct":
                translate_struct(types, constants, tag)
                continue
            if category == "union":
                translate_union(types, constants, tag)
                continue
            if tag.get("name") == "int": # This may kick back if someone
                continue                 # adds name="int" to some of the
                                         # registry-types field.
            if "requires" in tag.attrs:
                continue
            assert False, tag

    libvulkan["variables"] = variables = {}
    for tag in registry.commands:
        if tag.name == "command":
            translate_command(variables, constants, tag)

    for tag in registry.extensions:
        if tag.name == "extension":
            translate_extension(types, constants, tag)
            continue
        if tag.name is None:
            continue
        assert False, tag

    with open(vk_json, "w") as fd:
        json.dump(libvulkan, fd, sort_keys=True, indent=4)

def translate_api_constants(constants):
    for tag in constants:
        if tag.name == "enum":
            name = tag["name"]
            name = re.subn("^VK_", "", name)[0]
            value = tag["value"]
            value = re.subn(r"(\d*)\.(\d*)f", r"\1.\2", value)[0]
            # This may not be correct thing to do.. or then it is?
            value = re.subn(r"\(~0UL*\)", "-1", value)[0]
            value = re.subn(r"\(~0U-1\)", "-2", value)[0]
            if "." in value:
                yield name, float(value)
            else:
                yield name, int(value)

def translate_enumeration(types, enum, constructor):
    name = enum["name"]
    name = rename_enumeration(name)

    types[name] = this = {"type":constructor, "ctype":"i32"}
    this["constants"] = constants = {}

    # turns out the "expand" was insufficient nearly everywhere.
    prefix = "^VK_"
    for cell in split_case(name):
        prefix += "(" + cell.upper() + "_)?"
    for tag in enum:
        if tag.name == "enum":
            name_ = re.subn(prefix, "", tag["name"])[0]
            if "bitpos" in tag.attrs:
                value = 1 << int(tag["bitpos"])
            elif tag["value"].startswith("0x"):
                value = int(tag["value"], 16)
            else:
                value = int(tag["value"])
            constants[name_] = value
    return name

def rename_enumeration(name):
    name = re.subn("^Vk", "", name)[0]
    name = re.subn("FlagBits", "Flags", name)[0]
    return name

def translate_handle(types, tag):
    name = tag.find("name").text
    name = re.subn("^Vk", "", name)[0]
    if tag.type.text == u"VK_DEFINE_HANDLE":
        types[name] = {"type":"vulkan_handle", "dispatchable": True}
    elif tag.type.text == u"VK_DEFINE_NON_DISPATCHABLE_HANDLE":
        types[name] = {"type":"vulkan_handle", "dispatchable": False}
    else:
        assert False, "No translation for {!r} with <type> {!r}".format(name, tag.type.text)

def translate_funcpointer(types, constants, funcpointer):
    restype, name, args = vkparser.parse_funcpointer(funcpointer)
    name = re.subn("^PFN_vk", "PFN_", name)[0]
    types[name] = this = {"type":"cfunc"}
    this["restype"] = writeout_type(constants, restype)
    this["argtypes"] = argtypes = []

    for tp, n in args:
        argtypes.append(writeout_type(constants, restype))

def translate_struct(types, constants, struct):
    name = struct["name"]
    name = re.subn("^Vk", "", name)[0]
    types[name] = this = {"type":"struct"}
    this["fields"] = fields = []
    this["autoarrays"] = autoarrays = {}
    this["aliases"] = aliases = {}
    this["defaults"] = defaults = {}
    #has_sType = False
    for tag in struct:
        if tag.name == "member":
            tp, name_ = vkparser.parse_member(tag)
            fields.append([name_, writeout_type(constants, tp)])
            if "len" in tag.attrs and tag["len"] != "null-terminated" and not tag["len"].startswith("latexmath:"):
                counter = tag["len"].split(",", 1)[0]
                alias = re.sub('^p+([A-Z])', lambda m: m.group(1).lower(), name_)
                autoarrays[alias] = [counter, name_]
            elif re.match("^p+[A-Z]", name_) and name_ != "pNext":
                assert re.match("^p+[A-Z]", name_), name_
                alias = re.sub('^p+([A-Z])', lambda m: m.group(1).lower(), name_)
                aliases[alias] = name_
            if name_ == "sType":
                if "values" in tag.attrs:
                    defaults["sType"] = re.sub("^VK_STRUCTURE_TYPE_", "", tag["values"])
                else:
                    assert False, (name, "no value")
                    #defaults["sType"] = "_".join(x.upper() for x in split_case(name))

def translate_union(types, constants, struct):
    name = struct["name"]
    name = re.subn("^Vk", "", name)[0]
    types[name] = this = {"type":"union"}
    this["fields"] = fields = []
    for tag in struct:
        if tag.name == "member":
            tp, name_ = vkparser.parse_member(tag)
            fields.append([name_, writeout_type(constants, tp)])

def translate_command(variables, constants, tag):
    restype, cname = vkparser.parse_member(tag.proto)
    name = re.sub('^vk([A-Z]?)', lambda m: m.group(1).lower(), cname)

    variables[name] = command = {}
    command["name"] = cname
    command["type"] = ctype = {"type": "cfunc"}

    ctype["restype"] = writeout_type(constants, restype)
    ctype["argtypes"] = argtypes = []

    for param in tag:
        if param.name == "param":
            argtype, _ = vkparser.parse_member(param)
            argtypes.append(writeout_type(constants, argtype))

def translate_extension(types, constants, extension):
    enum_base = 1000000000 + 1000 * (int(extension["number"]) - 1)
    for tag in extension.require:
        if tag.name is None:
            continue
        if tag.name == "enum" and "value" in tag.attrs:
            value = tag["value"]
            if value in constants:
                value = constants[value]
            elif value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value == "VK_COLOR_SPACE_SRGB_NONLINEAR_KHR":
                value = types["ColorSpaceKHR"]["constants"]["SRGB_NONLINEAR_KHR"]
            elif value == "VK_STRUCTURE_TYPE_DEBUG_REPORT_CALLBACK_CREATE_INFO_EXT":
                value = types["StructureType"]["constants"]["DEBUG_REPORT_CALLBACK_CREATE_INFO_EXT"]
            elif value == "VK_DEBUG_REPORT_OBJECT_TYPE_DEBUG_REPORT_CALLBACK_EXT_EXT":
                value = types["DebugReportObjectTypeEXT"]["constants"]["DEBUG_REPORT_CALLBACK_EXT_EXT"]
            else:
                value = int(value)
            constants[tag["name"]] = value
            continue
        if tag.name == "enum" and "extends" in tag.attrs:
            extends = rename_enumeration(tag["extends"])
            prefix = "^VK_"
            for cell in split_case(extends):
                prefix += "(" + cell.upper() + "_)?"
            name = re.sub(prefix, "", tag["name"])
            if "offset" in tag.attrs:
                if tag.get("dir") == "-":
                    sign = -1
                else:
                    sign = +1
                const = sign * (enum_base + int(tag["offset"]))
            elif "bitpos" in tag.attrs:
                const = 1 << int(tag["bitpos"])
            else:
                assert False, tag
            types[extends]["constants"][name] = const
            continue
        if tag.name == "enum" and set(tag.attrs) == {"name"}:
            continue
        if tag.name == "command":
            continue
        if tag.name == "type":
            continue
        assert False, tag


def split_case(name):
    for cell in re.split("([A-Z0-9]+[a-z0-9]+)", name):
        if cell != "":
            yield cell

basetypes = dict(
    uint8_t = "u8",
    int32_t = "i32",
    uint32_t = "u32",
    uint64_t = "u64",
    float = "float",
    char = "char",
    size_t = "size_t",
    int = "int",
    void = "void",
    ANativeWindow = "void*",
    Display = "void*",
    MirConnection = "void*",
    MirSurface = "void*",
    struct_wl_display = "void",
    struct_wl_surface = "void",
    HINSTANCE = "void*",
    HANDLE = "void*",
    HWND = "void*",
    DWORD = "u32",
    LPCWSTR = "void*",
    Window = "void*",
    SECURITY_ATTRIBUTES = "void",
    xcb_connection_t = "void",
    xcb_window_t = "void*",
    VisualID = "void*",
    xcb_visualid_t = "void*",
    RROutput = "void",
)

def writeout_type(constantmap, node):
    if node.name == "struct":
        return basetypes["struct_" + node[0]]
    if node.name == "type":
        name = node[0]
        if name in typemap:
            return typemap[name]
        if name.startswith("Vk"):
            return rename_enumeration(name)
        if name.startswith("PFN_vk"):
            return "PFN_" + name[6:]
        return basetypes[name]
    if node.name == "array":
        return {
            "type":"array",
            "ctype": writeout_type(constantmap, node[0]),
            "length": writeout_constant(constantmap, node[1])}
    if node.name == "pointer":
        tp = writeout_type(constantmap, node[0])
        return {"type":"pointer", "to":tp}
    assert False, node

def writeout_constant(constantmap, node):
    if node.name == "enum":
        name = node[0]
        if name.startswith("VK_"):
            return constantmap[name[3:]]
    if node.name == "constant":
        return node[0]
    assert False, node

if __name__=="__main__":
    translate()
