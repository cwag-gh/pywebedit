//import terser from '@rollup/plugin-terser';
import {nodeResolve} from '@rollup/plugin-node-resolve'

export default {
    input: 'editor.mjs',
    output: {
        file: '../editor.bundle.min.js',
        format: 'iife',
//        sourcemap: true,
    },
    plugins: [
        nodeResolve()
//        resolve(), // Resolves node_modules
//        terser({
//            format: {
//                comments: false
//            },
//            compress: {
//                dead_code: true,
//                drop_console: true,
//                drop_debugger: true,
//                pure_funcs: ['console.log']
//            }
//        })
//    ],
        ]
//    treeshake: {
//        moduleSideEffects: false,
//        propertyReadSideEffects: false
//    }
}
