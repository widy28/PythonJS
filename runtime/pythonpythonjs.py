# PythonJS Low Level Runtime
# by Amirouche Boubekki and Brett Hartshorn - copyright 2013
# License: "New BSD"


__NULL_OBJECT__ = Object.create( null )
if 'window' in this and 'document' in this:
	__NODEJS__ = False
	pythonjs = {}
else:
	## note, we can not test for: '"process" in this' or '"process" in global'
	## make sure we are really inside NodeJS by letting this fail, and halting the program.
	__NODEJS__ = True
	print process.title
	print process.version


def jsrange(num):
	"""Emulates Python's range function"""
	var(i, r)
	i = 0
	r = []
	while i < num:
		r.push(i)
		i = i + 1
	return r


def create_array():
	"""Used to fix a bug/feature of Javascript where new Array(number)
	created a array with number of undefined elements which is not
	what we want"""
	var(array)
	array = []
	for i in jsrange(arguments.length):
		array.push(arguments[i])
	return array

def adapt_arguments(handler):
	"""Useful to transform Javascript arguments to Python arguments"""
	def func():
		handler(Array.prototype.slice.call(arguments))
	return func



def get_attribute(object, attribute):
	"""Retrieve an attribute, method, property, or wrapper function.

	method are actually functions which are converted to methods by
	prepending their arguments with the current object. Properties are
	not functions!

	DOM support:
		http://stackoverflow.com/questions/14202699/document-createelement-not-working
		https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/instanceof

	Direct JavaScript Calls:
		if an external javascript function is found, and it was not a wrapper that was generated here,
		check the function for a 'cached_wrapper' attribute, if none is found then generate a new
		wrapper, cache it on the function, and return the wrapper.
	"""
	if attribute == '__call__':
		if JS("{}.toString.call(object) === '[object Function]'"):
			if JS("object.pythonscript_function === true"):
				return object
			elif JS("object.is_wrapper !== undefined"):
				return object
			else:
				JS("var cached = object.cached_wrapper")
				if cached:
					return cached
				else:  ## TODO - double check if this still happens
					def wrapper(args,kwargs): return object.apply(None, args)  ## TODO, bind this?
					wrapper.is_wrapper = True
					object.cached_wrapper = wrapper
					return wrapper

	if Object.hasOwnProperty.call(object, '__getattribute__'):
		return object.__getattribute__( attribute )

	var(attr)
	attr = object[attribute]  ## this could be a javascript object with cached method

	if __NODEJS__ is False:
		if JS("object instanceof HTMLDocument"):
			#print 'DYNAMIC wrapping HTMLDocument'
			if JS("typeof(attr) === 'function'"):
				def wrapper(args,kwargs): return attr.apply(object, args)
				wrapper.is_wrapper = True
				return wrapper
			else:
				return attr
		elif JS("object instanceof HTMLElement"):
			#print 'DYNAMIC wrapping HTMLElement'
			if JS("typeof(attr) === 'function'"):
				def wrapper(args,kwargs): return attr.apply(object, args)
				wrapper.is_wrapper = True
				return wrapper
			else:
				return attr
		
	#if attribute in object:  ## in test not allowed with javascript-string
	if attr is not None:  ## what about cases where attr is None?
		if JS("typeof(attr) === 'function' && attr.pythonscript_function === undefined && attr.is_wrapper === undefined"):
			## to avoid problems with other generated wrapper funcs not marked with:
			## F.pythonscript_function or F.is_wrapper, we could check if object has these props:
			## bases, __name__, __dict__, __call__
			#print 'wrapping something external', object, attribute

			def wrapper(args,kwargs): return attr.apply(object, args)
			wrapper.is_wrapper = True
			return wrapper
		else:
			return attr

	var(__class__, bases)

	# next check object.__dict__ for attr, note that object could be a class, and classes have a __dict__
	#__dict__ = object.__dict__
	#if __dict__:
	#	attr = __dict__[attribute]
	#	if attr != None:
	#		return attr
	attr = object[ attribute ]
	if attr != None:
		return attr


	# next check for object.__class__
	__class__ = object.__class__
	if __class__:  ## at this point we can assume we are dealing with a pythonjs class instance

		if attribute in __class__.__properties__:  ## @property decorators
			return __class__.__properties__[ attribute ]['get']( [object], JSObject() )

		if attribute in __class__.__unbound_methods__:
			attr = __class__.__unbound_methods__[ attribute ]
			def method():
				var(args)
				args =  Array.prototype.slice.call(arguments)
				if (JS('args[0] instanceof Array') and JS("{}.toString.call(args[1]) === '[object Object]'") and args.length == 2):
					pass
				else:
					args = [args, JSObject()]
				args[0].splice(0, 0, object)
				return attr.apply(this, args)  ## this is bound so that callback methods can use `this` from the caller

			method.is_wrapper = True
			object[attribute] = method  ## cache method - we assume that methods do not change
			return method


		attr = __class__[ attribute ]

		if attribute in __class__:
			if JS("{}.toString.call(attr) === '[object Function]'"):
				def method():
					var(args)
					args =  Array.prototype.slice.call(arguments)
					if (JS('args[0] instanceof Array') and JS("{}.toString.call(args[1]) === '[object Object]'") and args.length == 2):
						pass
					else:
						# in the case where the method was submitted to javascript code
						# put the arguments in order to be processed by PythonJS
						args = [args, JSObject()]
					args[0].splice(0, 0, object)
					return attr.apply(this, args)
				method.is_wrapper = True

				object[attribute] = method  ## cache method - we assume that methods do not change

				return method
			else:
				return attr

		bases = __class__.__bases__

		for base in bases:
			attr = _get_upstream_attribute(base, attribute)
			if attr:
				if JS("{}.toString.call(attr) === '[object Function]'"):
					def method():
						var(args)
						args =  Array.prototype.slice.call(arguments)
						if (JS('args[0] instanceof Array') and JS("{}.toString.call(args[1]) === '[object Object]'") and args.length == 2):
							pass
						else:
							# in the case where the method was submitted to javascript code
							# put the arguments in order to be processed by PythonJS
							args = [args, JSObject()]

						args[0].splice(0, 0, object)
						return attr.apply(this, args)
					method.is_wrapper = True

					object[attribute] = method  ## cache method - we assume that methods do not change

					return method
				else:
					return attr

		for base in bases:  ## upstream property getters come before __getattr__
			var( prop )
			prop = _get_upstream_property(base, attribute)
			if prop:
				return prop['get']( [object], JSObject() )

		if '__getattr__' in __class__:
			return __class__['__getattr__']( [object, attribute], JSObject() )

		for base in bases:
			var( f )
			f = _get_upstream_attribute(base, '__getattr__')
			if f:
				return f( [object, attribute], JSObject() )


	if JS('object instanceof Array'):
		if attribute == '__getitem__':
			def wrapper(args,kwargs): return object[ args[0] ]
			wrapper.is_wrapper = True
			return wrapper
		elif attribute == '__setitem__':
			def wrapper(args,kwargs): object[ args[0] ] = args[1]
			wrapper.is_wrapper = True
			return wrapper

	elif attribute == '__getitem__':  ## this should be a JSObject - or anything else - is this always safe?
		def wrapper(args,kwargs): return object[ args[0] ]
		wrapper.is_wrapper = True
		return wrapper
	elif attribute == '__setitem__':
		def wrapper(args,kwargs): object[ args[0] ] = args[1]
		wrapper.is_wrapper = True
		return wrapper

	# raise AttributeError instead? or should we allow this? maybe we should be javascript style here and return undefined
	return None

def _get_upstream_attribute(base, attr):
	if attr in base:
		return base[ attr ]
	for parent in base.__bases__:
		return _get_upstream_attribute(parent, attr)

def _get_upstream_property(base, attr):  ## no longer required
	if attr in base.__properties__:
		return base.__properties__[ attr ]
	for parent in base.__bases__:
		return _get_upstream_property(parent, attr)

def set_attribute(object, attribute, value):
	'''
	__setattr__ is always called when an attribute is set,
	unlike __getattr__ that only triggers when an attribute is not found,
	this asymmetry is in fact part of the Python spec.
	note there is no __setattribute__

	In normal Python a property setter is not called before __setattr__,
	this is bad language design because the user has been more explicit
	in having the property setter.

	In PythonJS, property setters are called instead of __setattr__.
	'''

	if '__class__' in object and object.__class__.__setters__.indexOf(attribute) != -1:
		object[attribute] = value
	elif '__setattr__' in object:
		object.__setattr__( attribute, value )
	else:
		object[attribute] = value



def get_arguments(signature, args, kwargs):
	"""Based on ``signature`` and ``args``, ``kwargs`` parameters retrieve
	the actual parameters.

	This will set default keyword arguments and retrieve positional arguments
	in kwargs if their called as such"""

	if args is None:
		args = []
	if kwargs is None:
		kwargs = JSObject()
	out = JSObject()

	# if the caller did not specify supplemental positional arguments e.g. *args in the signature
	# raise an error
	if args.length > signature.args.length:
		if signature.vararg:
			pass
		else:
			print 'ERROR args:', args, 'kwargs:', kwargs, 'sig:', signature
			raise TypeError("Supplemental positional arguments provided but signature doesn't accept them")

	j = 0
	while j < signature.args.length:
		name = signature.args[j]
		if name in kwargs:
			# value is provided as a keyword argument
			out[name] = kwargs[name]
		elif j < args.length:
			# value is positional and within the signature length
			out[name] = args[j]
		elif name in signature.kwargs:
			# value is not found before and is in signature.length
			out[name] = signature.kwargs[name]
		j += 1

	args = args.slice(j)  ## note that if this fails because args is not an array, then a pythonjs function was called from javascript in a bad way.

	if signature.vararg:
		out[signature.vararg] = args
	if signature.varkwarg:
		out[signature.varkwarg] = kwargs
	return out

