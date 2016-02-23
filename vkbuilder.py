import ctypes

def load_vulkan():
    return ctypes.CDLL("libvulkan.so")

class VkType(object):
    ctype = None

    def blank(self):
        return get_ctype(self)()

    def array(self, count):
        return (get_ctype(self) * count)()

class Structure(VkType):
    def __init__(self, name):
        self.name = name
        self.fields = None
        self.autoarrays = {}
        self.aliases = {}
        self.sType = None

    def declare(self, fields):
        self.fields = fields
        self.lookup = dict(fields)

    def create_ctype(self):
        self.ctype = type(self.name.encode('utf-8'), (ctypes.Structure,), {})
        self.ctype._fields_ = [
            (name, get_ctype(value))
            for name, value in self.fields]

    def declare_autoarrays(self, autoarrays):
        self.autoarrays = dict(autoarrays)

    def declare_aliases(self, aliases):
        self.aliases = dict(aliases)

    def __call__(self, struct):
        ctype = get_ctype(self)
        obj = ctype()
        pool = PoolRecord(obj)
        ctypes.memset(ctypes.pointer(obj), 0, ctypes.sizeof(ctype))
        self.fill(pool, obj, struct)
        return pool

    def fill(self, pool, obj, struct):
        # todo: improve
        setcounters = set()
        for key, item in struct.iteritems():
            if key in self.autoarrays:
                counter, pointer = self.autoarrays[key]
                if counter in setcounters:
                    count = getattr(obj, counter)
                    if count != len(item):
                        raise Exception("Inconsistent record: {} = len({})".format(count, item))
                else:
                    setcounters.add(counter)
                    setattr(obj, counter, len(item))
                setattr(obj, pointer, self.lookup[pointer].autoarray(pool, item))
            else:
                key = self.aliases.get(key, key)
                field = self.lookup[key]
                if must_fill(field):
                    field.fill(pool, getattr(obj, key), item)
                else:
                    setattr(obj, key, auto(field, pool, item))
        if self.sType:
            obj.sType = auto(self.lookup["sType"], pool, self.sType)

class Union(VkType):
    def __init__(self, name):
        self.name = name
        self.fields = None

    def declare(self, fields):
        self.fields = fields
        self.lookup = dict(fields)

    def create_ctype(self):
        self.ctype = type(self.name.encode('utf-8'), (ctypes.Union,), dict(
            _fields_ = [
                (name, get_ctype(value))
                for name, value in self.fields]))

    def fill(self, pool, obj, struct):
        assert False, "todo"

class PoolRecord(object):
    def __init__(self, to):
        self.pool = []
        self.to = to

    def add(self, obj):
        self.pool.append(obj)
        return obj

class Enumeration(VkType):
    def __init__(self, name, table):
        self.name = name
        self.table = table
        self.inv_table = dict((y, x) for x, y in table.items())
        self.ctype = ctypes.c_int
    
    def __call__(self, value=0):
        return self.enum.inv_table.get(value, value)

    def from_param(self, param):
        if isinstance(param, (str, unicode)):
            return self.table[param]
        else:
            return param

    def auto(self, pool, value):
        return self.from_param(value)

class Bitmask(VkType):
    def __init__(self, name, table):
        self.name = name
        self.table = table
        self.inv_table = list((y, x) for x, y in table.items())
        self.ctype = ctypes.c_int

    def auto(self, pool, value):
        return self.from_param(value)

    def __call__(self, value=0):
        result = set()
        maskbits = 0
        for name, mask in self.table.iteritems():
            if value & mask == mask:
                result.add(name)
                maskbits |= mask
        if value ^ mask != 0:
            result.add(value)
        return result

    def from_param(self, param):
        if isinstance(param, (set, list)):
            if isinstance(param, (str, unicode)):
                return self.table[param]
            elif isinstance(param, (int, long)):
                return param
        else:
            value = 0
            for param in param:
                if isinstance(param, (str, unicode)):
                    value |= self.table[param]
                elif isinstance(param, (int, long)):
                    value |= param
            return value

class Handle(VkType):
    def __init__(self, name):
        self.name = name
        self.ctype = ctypes.c_void_p

    def from_param(self, param):
        if isinstance(param, HandlePtr) and param.handletype == self:
            return param.to
        # todo: improve
        return param

    def auto(self, pool, value):
        return self.from_param(value)

    def __call__(self, value=0):
        return HandlePtr(self, self.ctype(value))

class HandlePtr(object):
    def __init__(self, handletype, to):
        self.handletype = handletype
        self.to = to 

class FuncPointer(VkType):
    def __init__(self, name, restype, argtypes):
        self.name = name
        self.restype = restype
        self.argtypes = argtypes
        self.ctype = ctypes.CFUNCTYPE(restype, *argtypes)

    def __call__(self, value):
        return get_ctype(self)(value)

    def from_param(self, param):
        return param

    def auto(self, pool, value):
        return self.from_param(value)

class Array(VkType):
    def __init__(self, to, count):
        self.to = to
        self.count = count

    def create_ctype(self):
        self.ctype = get_ctype(self.to) * self.count

    def fill(self, pool, obj, struct):
        assert False, "todo"

    def __call__(self, value):
        return get_ctype(self)(value)

    def from_param(self, param):
        return param

class Pointer(VkType):
    def __init__(self, to):
        self.to = to

    def create_ctype(self):
        self.ctype = ctypes.POINTER(get_ctype(self.to))

    def from_param(self, param):
        if isinstance(param, PoolRecord):
            return ctypes.pointer(param.to)
        elif isinstance(param, HandlePtr):
            if param.handletype != self.to:
                raise Exception("Incompatible pointer: {}, {}".format(param.handletype, self.to))
            return ctypes.byref(param.to)
        elif param == None:
            return None
        else:
            return param

    def autoarray(self, pool, values):
        array = pool.add((get_ctype(self.to) * len(values))())
        if must_fill(self.to):
            for i, value in enumerate(values):
                self.to.fill(pool, array[i], value)
        else:
            for i, value in enumerate(values):
                array[i] = auto(self.to, pool, value)
        return array

    def auto(self, pool, value):
        if must_fill(self.to):
            obj = pool.add(get_ctype(self.to)())
            self.to.fill(pool, obj, value)
            return ctypes.pointer(obj)
        else:
            return value

def must_fill(field):
    return isinstance(field, (Union, Structure, Array))

def auto(field, pool, value):
    if isinstance(field, VkType):
        return field.auto(pool, value)
    return value

class AutoCheck(object):
    def __init__(self, enum, error):
        self.enum = enum
        self.error = error

    def __call__(self, value):
        if value == 0:
            return "SUCCESS"
        else:
            raise self.error(self.enum(value))

def get_ctype(obj):
    if isinstance(obj, VkType):
        if obj.ctype == None:
            obj.create_ctype()
        return obj.ctype
    return obj
