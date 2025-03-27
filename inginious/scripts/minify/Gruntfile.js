module.exports = function(grunt)
{
    // Project configuration.
    grunt.initConfig({
        pkg: grunt.file.readJSON('package.json'),
        concat: {
            options: {
                // define a string to put between each file in the concatenated output
                separator: '\n /* --- */ \n'
            },
            dist: {
                files: {
                    '../../inginious/frontend/static/js/all-minified.js': [
                        '../../inginious/frontend/static/js/libs/jquery.min.js',
                        '../../inginious/frontend/static/js/libs/jquery.form.min.js',
                        '../../inginious/frontend/static/js/libs/popper.min.js',
                        '../../inginious/frontend/static/js/libs/bootstrap.min.js',
                        '../../inginious/frontend/static/js/libs/moment.min.js',
                        '../../inginious/frontend/static/js/libs/bootstrap-datetimepicker.min.js',
                        '../../inginious/frontend/static/js/libs/Sortable.min.js',
                        '../../inginious/frontend/static/js/libs/jquery.twbsPagination.min.js',
                        '../../inginious/frontend/static/js/libs/selectize.min.js',
                        '../../inginious/frontend/static/js/codemirror/codemirror.js',
                        '../../inginious/frontend/static/js/codemirror/mode/meta.js',
                        '../../inginious/frontend/static/js/common.js',
                        '../../inginious/frontend/static/js/task.js',
                        '../../inginious/frontend/static/js/webapp.js',
                        '../../inginious/frontend/static/js/studio.js',
                        '../../inginious/frontend/static/js/audiences.js',
                        '../../inginious/frontend/static/js/groups.js',
                        '../../inginious/frontend/static/js/checked-list-group.js',
                        '../../inginious/frontend/static/js/task_dispensers.js',
                        '../../inginious/frontend/static/js/admin.js'
                    ],
                    '../../inginious/frontend/static/js/all-minified-rtl.js': [
                        '../../inginious/frontend/static/js/libs/jquery.min.js',
                        '../../inginious/frontend/static/js/libs/jquery.form.min.js',
                        '../../inginious/frontend/static/js/libs/popper.min.js',
                        '../../inginious/frontend/static/js/libs/bootstrap-rtl.min.js',
                        '../../inginious/frontend/static/js/libs/moment.min.js',
                        '../../inginious/frontend/static/js/libs/bootstrap-datetimepicker.min.js',
                        '../../inginious/frontend/static/js/libs/Sortable.min.js',
                        '../../inginious/frontend/static/js/libs/jquery.twbsPagination.min.js',
                        '../../inginious/frontend/static/js/libs/selectize.min.js',
                        '../../inginious/frontend/static/js/codemirror/codemirror.js',
                        '../../inginious/frontend/static/js/codemirror/mode/meta.js',
                        '../../inginious/frontend/static/js/common.js',
                        '../../inginious/frontend/static/js/task.js',
                        '../../inginious/frontend/static/js/webapp.js',
                        '../../inginious/frontend/static/js/studio.js',
                        '../../inginious/frontend/static/js/audiences.js',
                        '../../inginious/frontend/static/js/groups.js',
                        '../../inginious/frontend/static/js/checked-list-group.js',
                        '../../inginious/frontend/static/js/task_dispensers.js',
                        '../../inginious/frontend/static/js/admin.js'
                     ]
                }
            }
        },
        uglify: {
            options: {
                compress: true
            },
            dist: {
                files: {
                    '../../inginious/frontend/static/js/all-minified.js': ['../../inginious/frontend/static/js/all-minified.js'],
                    '../../inginious/frontend/static/js/all-minified-rtl.js': ['../../inginious/frontend/static/js/all-minified-rtl.js'],
                }
            }
        }
    });

    // Load the plugin that provides the "uglify" task.
    grunt.loadNpmTasks('grunt-contrib-uglify');
    grunt.loadNpmTasks('grunt-contrib-concat');
    grunt.loadNpmTasks('grunt-contrib-compress');

    // Default task(s).
    grunt.registerTask('default', ['concat', 'uglify']);
};
