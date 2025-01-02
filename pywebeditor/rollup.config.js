import terser from '@rollup/plugin-terser'
import {nodeResolve} from '@rollup/plugin-node-resolve'

export default {
    input: 'editor.mjs',
    output: {
        file: '../pywebeditor.min.js',
        format: 'iife'
    },
    plugins: [
        nodeResolve(),
        terser({
            format: {
                comments: false
            },
            compress: {
                dead_code: true,
                drop_console: true,
                drop_debugger: true,
                pure_funcs: ['console.log']
            }
        })
    ]
}
