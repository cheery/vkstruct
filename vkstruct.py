from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, Tag
import re, os
import vkparser
#import json
#import sys

vk_xml = "./spec/vk.xml"

def translate():
    print "# This file was automatically generated by vkstruct.py"
    print "# You may want to edit the generator rather than this file."
    print "import vkbuilder, ctypes"
    print
    print "SampleMask = ctypes.c_uint32"
    print "Bool32 = ctypes.c_uint32"
    print "DeviceSize = ctypes.c_uint64"
    print
    print "lib = vkbuilder.load_vulkan()"

    with open(vk_xml) as fd:
        soup = BeautifulSoup(fd.read(), 'xml')
    registry = soup.registry

    enumerations = set()
    for tag in registry:
        if tag.name == "enums":
            if tag.get("name") == "API Constants":
                translate_api_constants(tag)
                continue
            if tag.get("type") == "enum":
                name = translate_enumeration(tag, "vkbuilder.Enumeration")
                enumerations.add(name)
                continue
            if tag.get("type") == "bitmask":
                name = translate_enumeration(tag, "vkbuilder.Bitmask")
                enumerations.add(name)
                continue
            assert False, tag
    
    print "class VulkanError(Exception):"
    print "    def __init__(self, result):"
    print "        self.result = result"
    print "    "
    print "    def __str__(self):"
    print "        return str(self.result)"
    print "ResultCheck = vkbuilder.AutoCheck(Result, VulkanError)"

    epilogues = []
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
                if name not in enumerations and name:
                    print "{} = ctypes.c_uint32".format(name)
                continue
            if category == "handle":
                translate_handle(tag)
                continue
            if category == "enum":
                name = tag["name"]
                name = rename_enumeration(name)
                if name not in enumerations and name:
                    print "{} = ctypes.c_uint32".format(name)
                continue
            if category == "funcpointer":
                translate_funcpointer(tag)
                continue
            if category == "struct":
                epilogues.append(translate_struct(tag))
                continue
            if category == "union":
                epilogues.append(translate_union(tag))
                continue
            if tag.get("name") == "int": # This may kick back if someone
                continue                 # adds name="int" to some of the
                                         # registry-types field.
            if "requires" in tag.attrs:
                continue
            assert False, tag
    print
    for epilogue in epilogues:
        epilogue()

    for tag in registry.commands:
        if tag.name == "command":
            restype, cname = vkparser.parse_member(tag.proto)
            restype = format_type(restype)
            if restype == "Result":
                restype = "ResultCheck"
            name = re.sub('^vk([A-Z]?)', lambda m: m.group(1).lower(), cname)
            print
            print "try:"
            print "    {} = lib.{}".format(name, cname)
            print "except AttributeError as e: pass"
            print "else:"
            print "    {}.restype = {}".format(name, restype)
            print "    {}.argtypes = [ ".format(name)
            for param in tag:
                if param.name == "param":
                    argtype, _ = vkparser.parse_member(param)
                    argtype = format_type(argtype)
                    print "        {},".format(argtype)
            print "    ]"

def translate_api_constants(constants):
    for tag in constants:
        if tag.name == "enum":
            name = tag["name"]
            name = re.subn("^VK_", "", name)[0]
            value = tag["value"]
            value = re.subn(r"(\d*)\.(\d*)f", r"\1.\2", value)[0]
            # This may not be correct thing to do.. or then it is?
            value = re.subn(r"\(~0U-\)*", "(-1-", value)[0]
            value = re.subn(r"\(~0UL*\)", "-1", value)[0]
            print name, "=", value
    print

def translate_enumeration(enum, constructor):
    name = enum["name"]
    name = rename_enumeration(name)
    print "{0} = {1}({0!r}, {{".format(name, constructor)
    # turns out the "expand" was insufficient nearly everywhere.
    prefix = "^VK_"
    for cell in split_case(name):
        prefix += "(" + cell.upper() + "_)?"
    for tag in enum:
        if tag.name == "enum":
            name_ = re.subn(prefix, "", tag["name"])[0]
            if "bitpos" in tag.attrs:
                value = "1 << " + tag["bitpos"]
            else:
                value = tag["value"]
            print "    {!r:<50}: {!s},".format(name_, value)
    print "})"
    return name

def rename_enumeration(name):
    name = re.subn("^Vk", "", name)[0]
    name = re.subn("FlagBits", "Flags", name)[0]
    return name

def translate_handle(tag):
    name = tag.find("name").text
    name = re.subn("^Vk", "", name)[0]
    print "{0:<24} = vkbuilder.Handle({0!r})".format(name)

def translate_funcpointer(funcpointer):
    restype, name, args = vkparser.parse_funcpointer(funcpointer)
    name = re.subn("^PFN_vk", "PFN_", name)[0]
    print "{0} = vkbuilder.FuncPointer({0!r}, {1}, [".format(
        name, format_type(restype))
    for tp, n in args:
        print "    {},".format(format_type(tp))
    print "])"

def translate_struct(struct):
    name = struct["name"]
    name = re.subn("^Vk", "", name)[0]
    print "{0} = vkbuilder.Structure({0!r})".format(name)
    def epilogue():
        autoarrays = []
        aliases = []
        has_sType = False
        print "{0}.declare([".format(name)
        for tag in struct:
            if tag.name == "member":
                tp, name_ = vkparser.parse_member(tag)
                print "    ({!r}, {}),".format(name_, format_type(tp))
                if "len" in tag.attrs and tag["len"] != "null-terminated":
                    autoarrays.append((tag["len"].split(",", 1)[0], name_))
                elif re.match("^p+[A-Z]", name_) and name_ != "pNext":
                    aliases.append(name_)
                has_sType = has_sType or name_ == "sType"
        print "])"
        if len(autoarrays) > 0:
            print "{0}.declare_autoarrays([".format(name)
            for counter, pointer in autoarrays:
                if counter.startswith("latexmath:"):
                    continue
                assert re.match("^p+[A-Z]", pointer), pointer
                name_ = re.sub('^p+([A-Z])', lambda m: m.group(1).lower(), pointer)
                print "    ({!r}, ({!r}, {!r})),".format(name_, counter, pointer)
            print "])"
        if len(aliases) > 0:
            print "{0}.declare_aliases([".format(name)
            for pointer in aliases:
                assert re.match("^p+[A-Z]", pointer), pointer
                name_ = re.sub('^p+([A-Z])', lambda m: m.group(1).lower(), pointer)
                print "    ({!r}, {!r}),".format(name_, pointer)
            print "])"
        if has_sType:
            print "{}.sType = {!r}".format(name,
                "_".join((x.upper() for x in split_case(name))))
    return epilogue

def translate_union(struct):
    name = struct["name"]
    name = re.subn("^Vk", "", name)[0]
    print "{0} = vkbuilder.Union({0!r})".format(name)
    def epilogue():
        print "{0}.declare([".format(name)
        for tag in struct:
            if tag.name == "member":
                tp, name_ = vkparser.parse_member(tag)
                print "    ({!r}, {}),".format(name_, format_type(tp))
        print "])"
    return epilogue

def split_case(name):
    for cell in re.split("([A-Z]+[a-z]+)", name):
        if cell != "":
            yield cell

basetypes = dict(
    int = "ctypes.c_int",
    uint8_t = "ctypes.c_uint8",
    int32_t = "ctypes.c_int32",
    uint32_t = "ctypes.c_uint32",
    uint64_t = "ctypes.c_uint64",
    float = "ctypes.c_float",
    char = "ctypes.c_char",
    size_t = "ctypes.c_size_t",
    void = "None",
    ANativeWindow = "ctypes.c_void_p",
    Display = "ctypes.c_void_p",
    MirConnection = "ctypes.c_void_p",
    MirSurface = "ctypes.c_void_p",
    struct_wl_display = "None",
    struct_wl_surface = "None",
    HANDLE = "ctypes.c_void_p",
    HINSTANCE = "ctypes.c_void_p",
    SECURITY_ATTRIBUTES = "ctypes.c_void_p",
    DWORD = "ctypes.c_uint32",
    LPCWSTR = "ctypes.c_void_p",
    RROutput = "None",
    HWND = "ctypes.c_void_p",
    Window = "ctypes.c_void_p",
    xcb_connection_t = "None",
    xcb_window_t = "ctypes.c_void_p",
    VisualID = "ctypes.c_void_p",
    xcb_visualid_t = "ctypes.c_void_p",
)

def format_type(node):
    if node.name == "struct":
        return basetypes["struct_" + node[0]]
    if node.name == "type":
        name = node[0]
        if name.startswith("Vk"):
            return rename_enumeration(name)
        if name.startswith("PFN_vk"):
            return "PFN_" + name[6:]
        return basetypes[name]
    if node.name == "array":
        return "vkbuilder.Array({}, {})".format(
            format_type(node[0]),
            format_constant(node[1]))
    if node.name == "pointer":
        tp = format_type(node[0])
        if tp == "None":
            return "ctypes.c_void_p"
        if tp == "ctypes.c_char":
            return "ctypes.c_char_p"
        return "vkbuilder.Pointer({})".format(tp)
    assert False, node

def format_constant(node):
    if node.name == "enum":
        name = node[0]
        if name.startswith("VK_"):
            return name[3:]
    if node.name == "constant":
        return repr(node[0])
    assert False, node

if __name__=="__main__":
    translate()
