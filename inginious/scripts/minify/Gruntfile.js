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
                    '../../frontend/static/js/all-minified.js': [
                        '../../frontend/static/js/libs/jquery.min.js',
                        '../../frontend/static/js/libs/jquery.form.min.js',
                        '../../frontend/static/js/libs/popper.min.js',
                        '../../frontend/static/js/libs/bootstrap.min.js',
                        '../../frontend/static/js/libs/moment.min.js',
			'../../frontend/static/js/libs/moment-timezone-with-data.min.js',
                        '../../frontend/static/js/libs/bootstrap-datetimepicker.min.js',
                        '../../frontend/static/js/libs/Sortable.min.js',
                        '../../frontend/static/js/libs/jquery.twbsPagination.min.js',
                        '../../frontend/static/js/libs/selectize.min.js',
                        '../../frontend/static/js/codemirror/codemirror.js',
                        '../../frontend/static/js/codemirror/mode/meta.js',
                        '../../frontend/static/js/common.js',
                        '../../frontend/static/js/task.js',
                        '../../frontend/static/js/webapp.js',
                        '../../frontend/static/js/studio.js',
                        '../../frontend/static/js/audiences.js',
                        '../../frontend/static/js/groups.js',
                        '../../frontend/static/js/checked-list-group.js',
                        '../../frontend/static/js/task_dispensers.js',
                        '../../frontend/static/js/admin.js',
                        '../../frontend/static/js/mycourses.js'
                    ],
                    '../../frontend/static/js/all-minified-rtl.js': [
                        '../../frontend/static/js/libs/jquery.min.js',
                        '../../frontend/static/js/libs/jquery.form.min.js',
                        '../../frontend/static/js/libs/popper.min.js',
                        '../../frontend/static/js/libs/bootstrap-rtl.min.js',
                        '../../frontend/static/js/libs/moment.min.js',
			'../../frontend/static/js/libs/moment-timezone-with-data.min.js',
                        '../../frontend/static/js/libs/bootstrap-datetimepicker.min.js',
                        '../../frontend/static/js/libs/Sortable.min.js',
                        '../../frontend/static/js/libs/jquery.twbsPagination.min.js',
                        '../../frontend/static/js/libs/selectize.min.js',
                        '../../frontend/static/js/codemirror/codemirror.js',
                        '../../frontend/static/js/codemirror/mode/meta.js',
                        '../../frontend/static/js/common.js',
                        '../../frontend/static/js/task.js',
                        '../../frontend/static/js/webapp.js',
                        '../../frontend/static/js/studio.js',
                        '../../frontend/static/js/audiences.js',
                        '../../frontend/static/js/groups.js',
                        '../../frontend/static/js/checked-list-group.js',
                        '../../frontend/static/js/task_dispensers.js',
                        '../../frontend/static/js/admin.js',
                        '../../frontend/static/js/admin.js'
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
                    '../../frontend/static/js/all-minified.js': ['../../frontend/static/js/all-minified.js'],
                    '../../frontend/static/js/all-minified-rtl.js': ['../../frontend/static/js/all-minified-rtl.js'],
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
