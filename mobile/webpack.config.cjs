// CommonJS (.cjs) is required: the NativeScript CLI loads this via require(),
// and the repo root package.json sets "type": "module", so a plain .js here
// would be treated as ESM and fail with "require(...) is not a function".
const webpack = require('@nativescript/webpack')

module.exports = (env) => {
	webpack.init(env)

	return webpack.resolveConfig()
}
