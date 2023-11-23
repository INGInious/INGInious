//
// This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
// more information about the licensing of this file.
//
"use strict";


// Hacky fix for codemirror in collapsable elements
function refresh_codemirror()
{
    var t = this;
    setTimeout(function()
    {
        $('.CodeMirror', t).each(function(i, el)
        {
            el.CodeMirror.refresh();
        });
    }, 10);
}

/**
 * Load the studio, creating blocks for existing subproblems
 */
function studio_load(data)
{
    jQuery.each(data, function(pid, problem)
    {
        var template = "#subproblem_" + problem["type"];
        studio_create_from_template(template, pid);
        studio_init_template(pid, problem);
    });

    var collapsable = $('#tab_subproblems .card');
    collapsable.on('show.bs.collapse',refresh_codemirror);

    // Must be done *after* the event definition
    if(collapsable.length !== 1)
        collapsable.collapse('hide');

    $('form#edit_task_form').on('submit', function()
    {
        studio_submit();
        return false;
    });

    studio_update_environments();
    $('#environment-type').change(studio_update_environments);
}

function studio_update_environments() {
    var env_type = $('#environment-type').val();
    $('.environment-boxes').hide();
    $('#environment-box-'+env_type).show();
}

/**
 * Update the "files" tabs when editing a task
 */
function studio_update_file_tabs(data, method)
{
    if(data == undefined)
        data = {};
    if(method == undefined)
        method = "GET";
    jQuery.ajax({
        beforeSend: function()
                    {
                        $("#tab_file_list").html('Loading');
                    },
        success:    function(data)
                    {
                        $("#tab_file_list").replaceWith(data);
                    },
        method:     method,
        data:       data,
        url:        location.pathname + "/files"
    });
}

/**
 * Delete a file related to a task
 */
function studio_task_file_delete(path)
{
    if(!confirm("Are you sure you want to delete this?") || !studio_task_file_delete_tab(path))
        return;
    studio_update_file_tabs({"action": "delete", "path": path});
}

/**
 * Rename/move a file related to a task
 */
function studio_task_file_rename(path)
{
    var new_path = prompt("Enter the new path", path);
    if(new_path != null && studio_task_file_delete_tab(path))
        studio_update_file_tabs({"action": "rename", "path": path, "new_path": new_path});
}

/**
 * Create a file related to a task
 */
function studio_task_file_create()
{
    var new_path = prompt("Enter the path to the file", "newfile.sh");
    if(new_path != null && studio_task_file_delete_tab(new_path))
        studio_update_file_tabs({"action": "create", "path": new_path});
}

/**
 * Upload a new file for a task
 */
function studio_task_file_upload()
{
    $('#modal_file_upload').modal('hide');
    $('#task_upload_form').ajaxSubmit({
        beforeSend: function()
                    {
                        $("#tab_file_list").html('Loading');
                    },
        success:    function(data)
                    {
                        $("#tab_file_list").replaceWith(data);
                    },
        url:        location.pathname + "/files"
    });
}

//Stores data about opened tabs
var studio_file_editor_tabs = {};
var studio_file_editor_tabs_next_id = 0;

/**
 * Open a new tab for editing a file, if it does not exists yet
 */
function studio_task_file_open_tab(path)
{
    if(studio_file_editor_tabs[path] == undefined)
    {
        var tab_id = "task_file_editor_" + studio_file_editor_tabs_next_id;
        studio_file_editor_tabs_next_id += 1;
        studio_file_editor_tabs[path] = tab_id;

        var edit_file_tabs = $('#edit_file_tabs');
        edit_file_tabs.append('<li class="nav-item studio_file_editor_tab">' +
            '<a class="nav-link" href="#' + tab_id + '" aria-controls="editor" role="tab" data-toggle="tab"><i class="fa fa-file-code-o"></i>&nbsp; ' + path +
            ' <button type="button" class="closetab"><i class="fa fa-remove"></i></button>' +
            '</a></li>');
        $('a[href="#' + studio_file_editor_tabs[path] + '"] .closetab', edit_file_tabs).click(function()
        {
            studio_task_file_delete_tab(path)
        });

        $('#edit_file_tabs_content').append('<div role="tabpanel" class="tab-pane" id="' + tab_id + '">Loading...</div>');

        jQuery.ajax({
            success:  function(data)
                      {
                          var newtab = $("#" + tab_id);
                          if(data["error"] != undefined)
                          {
                              newtab.html('INGInious can\'t read this file.');
                              return;
                          }

                          newtab.html('<textarea id="' + tab_id + '_editor" class="form-control"></textarea>');

                          var newtab_editor = $("#" + tab_id + '_editor');
                          newtab_editor.val(data['content']);
                          newtab_editor.attr('name', path);

                          //try to find the mode for the editor
                          var mode = CodeMirror.findModeByFileName(path);
                          if(mode == undefined)
                          {
                              mode = "text/plain";

                              if(path === "/run") //the default interpreter is IPython
                                  mode = "python";

                              //verify if it is a UNIX executable file that starts with #!
                              if(data['content'].substring(0, 2) == "#!")
                              {
                                  var app = data['content'].split("\n")[0].substring(2).trim();

                                  //check in codemirror
                                  $.each(CodeMirror.modeInfo, function(key, val)
                                  {
                                      if(app.indexOf(val['name'].toLowerCase()) != -1)
                                          mode = val["mode"];
                                  });

                                  //else, check in our small hint-list
                                  if(mode == "text/plain")
                                  {
                                      var hintlist = {"bash": "shell", "sh": "shell", "zsh": "shell", "python": "python", "php": "php"};
                                      $.each(hintlist, function(key, val)
                                      {
                                          if(app.indexOf(key) != -1)
                                              mode = val;
                                      });
                                  }
                              }
                          }
                          else
                              mode = mode["name"];

                          registerCodeEditor(newtab_editor[0], mode, 20);
                      },
            method:   "GET",
            dataType: "json",
            data:     {"path": path, "action": "edit"},
            url:      location.pathname + "/files"
        });
    }
    $('a[href="#' + studio_file_editor_tabs[path] + '"]', edit_file_tabs).tab('show');
}

/**
 * Delete an opened tab
 */
function studio_task_file_delete_tab(path)
{
    if(studio_file_editor_tabs[path] != undefined)
    {
        if(path in codeEditors) {
            // Check if modified
            if (!codeEditors[path].isClean() && !confirm('You have unsaved change to this file. Do you really want to close it?'))
                return false;

            // Remove from list
            delete codeEditors[path];
        }

        var edit_file_tabs = $('#edit_file_tabs');
        if($('a[href="#' + studio_file_editor_tabs[path] + '"]', edit_file_tabs).hasClass('active'))
            $('li:eq(0) a', edit_file_tabs).tab('show');
        $('a[href="#' + studio_file_editor_tabs[path] + '"]', edit_file_tabs).parent().remove();
        $('#' + studio_file_editor_tabs[path]).remove();
        delete studio_file_editor_tabs[path];
    }
    return true;
}

/**
 * Display a message indicating the status of a save action
 */
function studio_display_task_submit_message(title, content, type, dismissible)
{
    var code = getAlertCode(title, content, type, dismissible);
    $('#task_edit_submit_status').html(code);

    if(dismissible)
    {
        window.setTimeout(function()
        {
            $("#task_edit_submit_status").children().fadeTo(1000, 0).slideUp(1000, function()
            {
                $(this).remove();
            });
        }, 3000);
    }
}

/**
 * Submit the form
 */
var studio_submitting = false;
function studio_submit()
{
    if(studio_submitting)
        return;
    studio_submitting = true;

    studio_display_task_submit_message("Saving...", "", "info", false);

    $('form#edit_task_form .subproblem_order').each(function(index, elem)
    {
        $(elem).val(index);
    });

    var error = "";
    $('.task_edit_submit_button').attr('disabled', true);

    $.each(codeEditors, function(path, editor) {
        if(path in studio_file_editor_tabs) {
            jQuery.ajax({
                success: function (data) {
                    if ("error" in data)
                        error += "<li>An error occurred while saving the file " + path + "</li>";
                    else
                        editor.markClean();
                },
                url: location.pathname + "/files",
                method: "POST",
                dataType: "json",
                data: {"path": path, "action": "edit_save", "content": editor.getValue()},
                async: false
            });
        }
    });

    $('form#edit_task_form').ajaxSubmit({
        dataType: 'json',
        success: function (data) {
            if ("status" in data && data["status"] == "ok")
                error += "";
            else if ("message" in data)
                error += "<li>" + data["message"] + "</li>";
            else
                error += "<li>An internal error occurred</li>";
        },
        error: function () {
            error += "<li>An internal error occurred</li>";
        },
        async: false
    });

    if(error)
        studio_display_task_submit_message("Some error(s) occurred when saving the task: <ul>" + error + "</ul>", "", "danger", true);
    else
        studio_display_task_submit_message("Task saved.", "", "success", true);

    $('.task_edit_submit_button').attr('disabled', false);
    studio_submitting = false;
}

/**
 * Create new subproblem from the data in the form
 */
function studio_create_new_subproblem()
{
    var new_subproblem_pid = $('#new_subproblem_pid').val();
    var new_subproblem_type = $('#new_subproblem_type').val();
    if(!new_subproblem_pid.match(/^[a-zA-Z0-9_\-]+$/))
    {
        alert('Problem id should only contain alphanumeric characters (in addition to "_" and "-").');
        return;
    }

    if($(studio_get_problem(new_subproblem_pid)).length != 0)
    {
        alert('This problem id is already used.');
        return;
    }

    studio_create_from_template('#' + new_subproblem_type, new_subproblem_pid);
    studio_init_template(new_subproblem_pid, {"type": new_subproblem_type.substring(11)});

    $('#tab_subproblems .card').on('show.bs.collapse',refresh_codemirror);
}

/**
 * Create a new template and put it at the bottom of the problem list
 * @param template
 * @param pid
 */
function studio_create_from_template(template, pid)
{
    var tpl = $(template).html().replace(/PID/g, pid);
    var tplElem = $(tpl);
    $('#accordion').append(tplElem);
}

/**
 * Get the real id of the DOM element containing the problem
 * @param pid
 */
function studio_get_problem(pid)
{
    return "#subproblem_well_" + pid;
}

/**
 * Init a template with data from an existing problem
 * @param template
 * @param pid
 * @param problem
 */
function studio_init_template(pid, problem)
{
    var well = $(studio_get_problem(pid));

    //Default for every problem types
    if("name" in problem)
        $('#name-' + pid, well).val(problem["name"]);
    var header_editor = registerCodeEditor($('#header-' + pid)[0], 'rst', 10);
    if("header" in problem)
        header_editor.setValue(problem["header"]);

    //Custom values for each problem type
    window["studio_init_template_" + problem["type"] ](well, pid, problem);
}

/**
 * Init a code template
 * @param well: the DOM element containing the input fields
 * @param pid
 * @param problem
 */
function studio_init_template_code(well, pid, problem)
{
    if("language" in problem)
        $('#language-' + pid, well).val(problem["language"]);
    if("type" in problem)
        $('#type-' + pid, well).val(problem["type"]);
    if("optional" in problem && problem["optional"])
        $('#optional-' + pid, well).attr('checked', true);

    var default_tag = $('#default-' + pid)[0];
    var default_editor = registerCodeEditor(default_tag, 'text', default_tag.tagName === "INPUT" ? 1 : 10);
    if("default" in problem)
        default_editor.setValue(problem["default"]);
    if("offset" in problem)
        $('#offset-' + pid, well).val(problem["offset"]);
}

/**
 * Init a code single line template
 * @param well: the DOM element containing the input fields
 * @param pid
 * @param problem
 */
function studio_init_template_code_single_line(well, pid, problem)
{
    studio_init_template_code(well, pid, problem);
}

/**
 * Init a file template
 * @param well: the DOM element containing the input fields
 * @param pid
 * @param problem
 */
function studio_init_template_file(well, pid, problem)
{
    if("max_size" in problem)
        $('#maxsize-' + pid, well).val(problem["max_size"]);
    if("allowed_exts" in problem)
        $('#extensions-' + pid, well).val(problem["allowed_exts"].join());
}

/**
 * Init a match template
 * @param well: the DOM element containing the input fields
 * @param pid
 * @param problem
 */
function studio_init_template_match(well, pid, problem)
{
    if("centralize" in problem && problem["centralize"])
        $('#centralize-' + pid, well).attr('checked', true);
    if("answer" in problem)
        $('#answer-' + pid, well).val(problem["answer"]);
}

/**
 * Init a multiple choice template
 * @param well: the DOM element containing the input fields
 * @param pid
 * @param problem
 */
function studio_init_template_multiple_choice(well, pid, problem)
{
    if("limit" in problem)
        $('#limit-' + pid, well).val(problem["limit"]);
    else
        $('#limit-' + pid, well).val(0);
    if("multiple" in problem && problem["multiple"])
        $('#multiple-' + pid, well).attr('checked', true);
    if("centralize" in problem && problem["centralize"])
        $('#centralize-' + pid, well).attr('checked', true);
    if("unshuffle" in problem && problem["unshuffle"])
        $('#unshuffle-' + pid, well).attr('checked', true);

    var success_message = "";
    var error_message = "";
    if("success_message" in problem)
        success_message = problem["success_message"];
    if("error_message" in problem)
        error_message = problem["error_message"];

    registerCodeEditor($('#success_message-' + pid)[0], 'rst', 1).setValue(success_message);
    registerCodeEditor($('#error_message-' + pid)[0], 'rst', 1).setValue(error_message);

    jQuery.each(problem["choices"], function(index, elem)
    {
        studio_create_choice(pid, elem);
    });
}

/**
 * Create a new choice in a given multiple-choice problem
 * @param pid
 * @param choice_data
 */
function studio_create_choice(pid, choice_data) {
    var well = $(studio_get_problem(pid));

    var index = 0;
    while($('#choice-' + index + '-' + pid).length != 0)
        index++;

    var row = $("#subproblem_multiple_choice_choice").html();
    var new_row_content = row.replace(/PID/g, pid).replace(/CHOICE/g, index);
    var new_row = $("<div></div>").attr('id', 'choice-' + index + '-' + pid).html(new_row_content);
    $("#choices-" + pid, well).append(new_row);

    var editor = registerCodeEditor($(".subproblem_multiple_choice_text", new_row)[0], 'rst', 1);
    var editor_feedback = registerCodeEditor($(".subproblem_multiple_choice_feedback", new_row)[0], 'rst', 1);

    if("text" in choice_data)
        editor.setValue(choice_data["text"]);
    if("feedback" in choice_data)
        editor_feedback.setValue(choice_data["feedback"]);

    if("valid" in choice_data && choice_data["valid"] == true) {
        studio_toggle_choice($(".subproblem_multiple_choice_valid", new_row).attr('name'));
    }
}

/**
 * Toggle multiple choice valid field
 * @param input_name Name of the checkbox input
 */
function studio_toggle_choice(input_name) {
    var checkbox = $("input[name='" + input_name + "']");
    checkbox.click();
    var btn = checkbox.next("button");
    btn.toggleClass("btn-danger");
    btn.toggleClass("btn-success");
    var icon = btn.find("i");
    icon.toggleClass("fa-times");
    icon.toggleClass("fa-check");
}

/**
 * Delete a multiple choice answer
 * @param pid
 * @param choice
 */
function studio_delete_choice(pid, choice)
{
    $('#choice-' + choice + '-' + pid).detach();
}

/**
 * Move subproblem up
 * @param pid
 */
function studio_subproblem_up(pid)
{
    var well = $(studio_get_problem(pid));
    var prev = well.prev();
    if(prev.length) {
        well.fadeOut(400, function() {
            well.detach().insertBefore(prev).fadeIn(400);
        });
    }
}

/**
 * Move subproblem down
 * @param pid
 */
function studio_subproblem_down(pid)
{
    var well = $(studio_get_problem(pid));
    var next = well.next();
    if(next.length) {
        well.fadeOut(400, function() {
            well.detach().insertAfter(next).fadeIn(400);
        });
    }
}

/**
 * Delete subproblem
 * @param pid
 */
function studio_subproblem_delete(pid)
{
    var well = $(studio_get_problem(pid));
    if(!confirm(delete_subproblem_message))
        return;
    $.each(codeEditors, function(name, editor)
    {
        if(jQuery.contains(well[0], editor.getTextArea()))
            delete codeEditors[name];
    });
    well.detach();
}

/**
 * Shows the feedback for an old submission
 */
var loadingSomething = false;
function studio_get_feedback(sid)
{
    if(loadingSomething)
        return;
    loadingSomething = true;
    $('#modal_feedback_content').text('Loading...');
    $('#modal_feedback').modal('show');

    $.getJSON(document.location.pathname + '/' + sid).done(function(data)
    {
        if(data['status'] == "ok")
        {
            var output = "<h4><b>Result</b></h4>";
            output += data["data"]["result"] + " - " + data["data"]["grade"] + "%";
            output += "<hr/><h4><b>Feedback - top</b></h4>";
            output += data["data"]["text"];
            $.each(data["data"]["problems"], function(index, elem)
            {
                output += "<hr/><h4><b>Feedback - subproblem " + index + "</b></h4>";
                output += elem;
            });
            output += "<hr/><h4><b>Debug</b></h4>";
            output += "<div id='modal_feedback_debug'></div>";

            $('#modal_feedback_content').html(output);
            displayDebugInfoRecur(data["data"], $('#modal_feedback_debug'));
        }
        else
        {
            $('#modal_feedback_content').text('An error occurred while retrieving the submission');
        }
        loadingSomething = false;
    }).fail(function()
    {
        $('#modal_feedback_content').text('An error occurred while retrieving the submission');
        loadingSomething = false;
    });
}

/*
 * Functions for tags edition. Use in tags.html
 */

function studio_expand_description(elem){
    elem.rows = 5;
}
function studio_expand_description_not(elem){
    elem.rows = 1;
}
// Add a new line to the tag table
function studio_add_table_line(line,target,target_blank_row) {

    var new_row = $("#"+target_blank_row).clone();
    var new_id = 1 + parseInt($('#'+target+' tr:last').attr('id'));
    if (isNaN(new_id))
        new_id = 0
            
    var modified_row = new_row.html();
    while(modified_row.includes("NEW")){
        modified_row = modified_row.replace("NEW", new_id);
    }
    while(modified_row.includes("disabled")){
        modified_row = modified_row.replace("disabled", "");
    }
    
    //ID, NAME, DESCRIPTION
    modified_row = modified_row.replace("ID_REPLACE", $('#A-'+line).text());
    modified_row = modified_row.replace("NAME_REPLACE", $('#B-'+line).text());
    modified_row = modified_row.replace("DESCRIPTION_REPLACE", $('#C-'+line).text());
    
    //VISIBILITY
    var visibility = "";
    if ($('#D-'+line).text() == "True"){
        visibility = "checked='checked'";
    }
    modified_row = modified_row.replace("visible_replace", visibility);
    
    //TYPE
    var type = $('#E-'+line).attr("data-type");
    modified_row = modified_row.replace("type_replace_"+type, 'selected="selected"');
    modified_row = modified_row.replace("id_stop", "");

    $('#'+target).find('tbody').append("<tr id="+new_id+">" + modified_row + "</tr>");
    new_row.show();
}


function drag_drop_handler() {
    // preventing page from redirecting
    $("html").on("dragover", function(e) {
        e.preventDefault();
        e.stopPropagation();
    });

    $("html").on("drop", function(e) { e.preventDefault(); e.stopPropagation(); });

    // Drag enter
    $(".upload-area").on('dragenter', function (e) {
        $("#dragtext").css("visibility", "visible");
        $(this).addClass("dragin");
        e.stopPropagation();
        e.preventDefault();
    });

    // Drag over
    $(".upload-area").on('dragover', function (e) {
        $(this).addClass("dragin");
        $("#dragtext").css("visibility", "visible");
        e.stopPropagation();
        e.preventDefault();

    });

    $(".upload-area").on('dragleave',function(e){
        $(this).removeClass("dragin");
        $("#dragtext").css("visibility", "hidden");
        e.stopPropagation();
        e.preventDefault();
    });

    // Drop
    $(".upload-area").on('drop', function (e) {
        $("#dragtext").css("visibility", "hidden");
        e.stopPropagation();
        e.preventDefault();

        var file = e.originalEvent.dataTransfer.files;
        var fd = new FormData();
        fd.append('file', file[0]);
        fd.append('name',file[0].name);
        uploadData(fd);
    });

    // file selected
    $("#file").change(function(){
        var fd = new FormData();
        var files = $('#file')[0].files[0];
        fd.append('file',files);
        uploadData(fd);
    });
}

// Sending AJAX request and upload file
function uploadData(formdata){
    $.ajax({
        url: window.location.href+'/dd_upload',
        type: 'post',
        data: formdata,
        contentType: false,
        processData: false,
        dataType: 'json',
        success: function(response){
            alert("uploaded!");
            studio_update_file_tabs(undefined, undefined);
        },
        error: function () {
            console.log("something went wrong");
        }
    });
}

// Use selectize.js to select for a user.
// element is the element to be used as a selector ($('#id'))
// path_to_search_user is the path to the search_user page (/admin/tutorial/search_user/) with the final /
// current_users is an array of dict with the format [{'username': 'theusername', 'realname': 'The realname'}]
// single: true for single user selection, false for multiple.
function user_selection(element, path_to_search_user, current_users, single) {
    element.selectize({
        delimiter: ',',
        persist: false,
        valueField: 'username',
        labelField: 'realname',
        searchField: ['username', 'realname'],
        create: false,
        options: current_users.map(function(x) { return {"username": x.username, "realname": x.realname + " (" + x.username + ")"} }),
        items: current_users.map(function(x) { return x.username }),
        load: function(query, callback) {
            if (!query.length) return callback();
            $.ajax({
                url: path_to_search_user + encodeURIComponent(query),
                type: 'GET',
                error: function() {
                    callback();
                },
                success: function(res) {
                    callback(res[0].map(function(x) { return {"username": x.username, "realname": x.realname + " (" + x.username + ")"} }));
                }
            });
        },
        maxItems: single ? 1 : null
    });
}
