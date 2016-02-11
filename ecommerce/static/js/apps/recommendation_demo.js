require([
        'jquery',
        'dataTablesBootstrap',
        'select2'
    ],
    function ($) {
        'use strict';

        function templateCourse(result) {
            return result.id + ' - ' + result.name;
        }

        function initializeTable($table, url) {
            return $table.DataTable({
                ajax: {
                    url: url,
                    dataSrc: ''
                },
                bFilter: false,
                bPaginate: false,
                columns: [
                    {data: 'weight', sTitle: 'Weight'},
                    {data: 'id', sTitle: 'Course ID'},
                    {data: 'name', sTitle: 'Course Title'}
                ],
                order: [
                    [0, 'desc'],
                    [1, 'asc']
                ],
                processing: true
            })

        }

        $(function () {
            var $courseSpecificForm = $('.course-specific form'),
                $courseField = $courseSpecificForm.find('select'),
                $userSpecificForm = $('.user-specific form'),
                $usernameField = $userSpecificForm.find('input'),
                $courseTable = null,
                $userTable = null;

            $courseField.select2({
                ajax: {
                    url: '/api/demo/courses/',
                    dataType: 'json',
                    delay: 250,
                    data: function (params) {
                        return {
                            q: params.term
                        };
                    },
                    minimumInputLength: 2,
                    cache: true
                },
                templateResult: templateCourse,
                templateSelection: templateCourse
            });

            $courseSpecificForm.submit(function (e) {
                var url = '/api/demo/courses/' + $courseField.val() + '/recommendations/';

                e.preventDefault();

                if ($courseTable) {
                    $courseTable.ajax.url(url).load();
                } else {
                    $courseTable = initializeTable($('.course-specific table.recommendations'), url);
                }
            });

            $userSpecificForm.submit(function (e) {
                var url = '/api/demo/users/' + $usernameField.val() + '/recommendations/';

                e.preventDefault();

                if ($userTable) {
                    $userTable.ajax.url(url).load();
                } else {
                    $userTable = initializeTable($('.user-specific table.recommendations'), url);
                }
            });
        });
    }
);
