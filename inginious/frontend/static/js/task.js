//
// This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
// more information about the licensing of this file.
//
"use strict";

function init_task_page(evaluate)
{
    evaluatedSubmission = evaluate;

    //Init the task form, if we are on the task submission page
    var task_form = $('form#task');
    task_form.on('submit', function() {
        submitTask(false);
        return false;
    });

    //Init the button that start a remote ssh server for debugging
    $('form#task #task-submit-debug').on('click', function() {
        submitTask(true);
    });

    //if INGInious tells us to wait for another submission
    //this takes precedence over the link in the URL, in order to be consistent.
    if(task_form.attr("data-wait-submission")) {
        loadOldSubmissionInput(task_form.attr("data-wait-submission"), false);
        waitForSubmission(task_form.attr("data-wait-submission"));
    }
    else {
        // Check if the page link contains a submission id to load, if needed
        try {
            // the class URLSearchParams may not exist in older browsers...
            var loadFromURL = (new URLSearchParams(document.location.search.substring(1))).get("load");
            if(loadFromURL !== null)
                loadOldSubmissionInput(loadFromURL, true);
        }
        catch(error) {
          console.error(error);
        }
    }

    $('.submission').each(function() {
        $(this).on('click', clickOnSubmission);
    });

    // Allows to close cards
    $(document).on('click', '[data-dismiss="card"]', function(event) {event.target.closest('.card').remove()});
}

var evaluatedSubmission = 'best';
//True if loading something
var loadingSomething = false;

//Blur task form
function blurTaskForm()
{
    $.each(codeEditors, function(idx, editor)
    {
        editor.setOption("readOnly", true);
    });
    var task_form = $('form#task');
    $("input, button", task_form).attr("disabled", "disabled").addClass('form-blur');
    //task_form.addClass('form-blur');
    loadingSomething = true;
}

function unblurTaskForm()
{
    $.each(codeEditors, function(idx, editor)
    {
        editor.setOption("readOnly", false);
    });
    var task_form = $('form#task');
    $("input, button", task_form).removeAttr("disabled").removeClass('form-blur');
    //task_form.removeClass('form-blur');
    loadingSomething = false;
}

//Reset all alerts
function resetAlerts()
{
    $('#task_alert').html('');
    $('.task_alert_problem').html('');
}

//Increment tries count
function incrementTries()
{
    var ttries = $('#task_tries');
    ttries.text(parseInt(ttries.text()) + 1);
}

//Update task status
function updateTaskStatus(newStatus, grade)
{
    var task_status = $('#task_status');
    var task_grade = $('#task_grade');

    task_status.html(newStatus);
    task_grade.text(grade);
}

//Creates a new submission (right column)
function displayNewSubmission(id)
{
    var submissions = $('#submissions');
    submissions.find('.submission-empty').remove();

    var submission_link = jQuery('<li/>', {
        class: "submission list-group-item list-group-item-warning",
        "data-submission-id": id
    }).on('click', clickOnSubmission);

    jQuery('<span id="txt"/>', {}).text(getDateTime()).appendTo(submission_link);
    
    //If there exists tags, we add a badge with '0' in the new submission.
    if($('span', $('#main_tag_group')).length > 0){
        submission_link.prepend('<span class="badge alert-info" id="tag_counter" >0</span> ');
    }

    submissions.prepend(submission_link);

    $("body").tooltip({
        selector: '[data-toggle="tooltip"]'
    });
}

function removeSubmission(id) {
    var item;

    $('#submissions').find('.submission').each(function() {
        if($(this).attr('data-submission-id').trim() == id)
            item = $(this)
    });

    item.remove();
}

//Updates a loading submission
function updateSubmission(id, result, grade, tags)
{
    grade = grade || "0.0";

    var nclass = "";
    if(result == "success") nclass = "list-group-item-success";
    else if(result == "save") nclass = "list-group-item-save";
    else nclass = "list-group-item-danger";
    $('#submissions').find('.submission').each(function()
    {
        if($(this).attr('data-submission-id').trim() == id)
        {
            $(this).removeClass('list-group-item-warning').addClass(nclass);
            var date = $(this).find("span[id='txt']");
            date.text(date.text() + " - " + grade + "%");
            
            //update the badge
            updateTagsToNewSubmission($(this), tags);  
        }
    });
}

// Change the evaluated submission displayed
function displayEvaluatedSubmission(id, fade) {
    var item;

    $('#submissions').find('.submission').each(function() {
        if($(this).attr('data-submission-id').trim() == id)
            item = $(this)
    });

    // LTI does not support selecting a specific submission for evaluation
    if($("#my_submission").length) {
        var text = item.find("span[id='txt']").html();
        var submission_link = jQuery('<a/>', {
            href: "#",
            id: "my_submission",
            class: "submission list-group-item list-group-item-action list-group-item-info",
            "data-submission-id": id
        }).on('click', clickOnSubmission);

        jQuery('<i/>', {class: "fa fa-chevron-right fa-fw"}).appendTo(submission_link).after("&nbsp;");
        submission_link.append(text);

        if (fade) {
            $("#my_submission").fadeOut(function () {
                $(this).replaceWith(submission_link.fadeIn().removeAttr('style'));
            });
        } else {
            $("#my_submission").replaceWith(submission_link);
        }

    }

    updateTaskStatus(item.hasClass("list-group-item-success") ? "Succeeded" : "Failed", parseFloat(item.text().split("-")[1]));
}

//Submission's click handler
function clickOnSubmission()
{
    if(loadingSomething)
        return;
    loadOldSubmissionInput($(this).attr('data-submission-id'), true);
    $('body').removeClass('sidebar-active');
}

//Get current datetime
function getDateTime()
{
    var MyDate = new Date();

    return ('0' + MyDate.getDate()).slice(-2) + '/'
        + ('0' + (MyDate.getMonth() + 1)).slice(-2) + '/'
        + MyDate.getFullYear() + " "
        + ('0' + MyDate.getHours()).slice(-2) + ':'
        + ('0' + MyDate.getMinutes()).slice(-2) + ':'
        + ('0' + MyDate.getSeconds()).slice(-2);
}

//Verify the task form (files, ...)
function taskFormValid()
{
    var answered_to_all = true;
    var errors = [];
    var form = $('#task');

    form.find('textarea,input[type="text"]').each(function()
    {
        if($(this).attr('name') != undefined) //skip codemirror's internal textareas
        {
            if($(this).val() == "" && $(this).attr('data-optional') != "True")
                answered_to_all = false;
        }
    });

    form.find('input[type="checkbox"],input[type="radio"]').each(function()
    {
        if(form.find("input[name='"+ $(this).attr('name')+"']:checked").length == 0)
        {
            answered_to_all = false;
        }
    });

    form.find('input[type="file"]').each(function()
    {
        var filename = $(this).val().split(/(\\|\/)/g).pop();

        //file input fields cannot be optional
        if(filename == "")
        {
            answered_to_all = false;
            return;
        }

        //verify ext
        var allowed_extensions = $.parseJSON($(this).attr('data-allowed-exts'));
        var has_one = false;
        $.each(allowed_extensions, function(idx, ext){
            has_one = has_one || (filename.lastIndexOf(ext) === filename.length - ext.length) > 0;
        });
        if(!has_one)
            errors.push($("#invalidext").text().replace("{}", filename));

        //try to get the size of the file
        var size = -1;
        try { size = $(this)[0].files[0].size; } catch (e) {} //modern browsers
        if(size == -1) try { size = $(this)[0].files[0].fileSize; } catch(e) { } //old versions of Firefox

        //Verify the maximum size
        var max_size = parseInt($(this).attr('data-max-size'));
        if(size != -1 && size > max_size)
            errors.push($("#filetooheavy").text().replace("{}", filename));
    });

    if(!answered_to_all)
    {
        errors.push($("#answerall").text());
    }

    if(errors.length != 0)
    {
        var task_alert = $('#task_alert');
        var content = $('<div></div>');
        var first = true;
        $.each(errors, function(idx, elem){
            if(!first)
                content.append($('<br>'));
            first = false;
            content.append($('<span></span>').text(elem));
        });
        task_alert.html(getAlertCode("Error", content.html(), "danger", false));
        $('html, body').animate({
            scrollTop: task_alert.offset().top - 100
        }, 200);
        return false;
    }
    else
    {
        return true;
    }
}

//Submits a task
function submitTask(with_ssh)
{
    if(loadingSomething)
        return;

    if(!taskFormValid())
        return;

    $('#task-debug-mode').val(with_ssh ? "ssh" : "");

    //Must be done before blurTaskForm as when a form is disabled, no input is sent by the plugin
    $('form#task').ajaxSubmit(
        {
            dataType: 'json',
            success:  function(data)
                      {
                          if("status" in data && data["status"] == "ok" && "submissionid" in data)
                          {
                              displayTaskLoadingAlert(data, data["submissionid"]);
                              incrementTries();
                              displayNewSubmission(data['submissionid']);
                              waitForSubmission(data['submissionid']);
                          }
                          else if("status" in data && data['status'] == "error" && "text" in data)
                          {
                              displayTaskStudentAlertWithProblems(data, "danger", false);
                              updateTaskStatus(data["text"], 0);
                              unblurTaskForm();
                          }

                          if("remove" in data) {
                              data["remove"].forEach(function(element, index, array) {
                                 removeSubmission(element);
                              });
                          }
                      },
            error:    function()
                      {
                          displayTaskStudentAlertWithProblems($("#internalerror").text(), "danger", false);
                          updateTaskStatus($("#internalerror").text(), 0);
                          unblurTaskForm();
                      }
        });

    blurTaskForm();
    resetAlerts();
    displayTaskLoadingAlert(null, null);
    updateTaskStatus("<i class=\"fa fa-spinner fa-pulse fa-fw\" aria-hidden=\"true\"></i>", 0);
    $('html, body').animate({
        scrollTop: $('#task_alert').offset().top - 100
    }, 200);
}

//Wait for a job to end
function waitForSubmission(submissionid)
{
    setTimeout(function()
    {
        var url = $('form#task').attr("action");
        jQuery.post(url, {"@action": "check", "submissionid": submissionid}, null, "json")
            .done(function(data)
            {
                if("status" in data && data['status'] === "waiting")
                {
                    waitForSubmission(submissionid);
                    if("ssh_host" in data && "ssh_port" in data && "ssh_user" in data && "ssh_password" in data)
                        displayRemoteDebug(submissionid, data);
                    else
                        displayTaskLoadingAlert(data, submissionid);

                }
                else if("status" in data && "result" in data && "grade" in data)
                {
                    updateMainTags(data);
                    if("debug" in data)
                        displayDebugInfo(data["debug"]);

                    if(data['result'] == "failed")
                        displayTaskStudentAlertWithProblems(data, "danger", false);
                    else if(data['result'] == "success")
                        displayTaskStudentAlertWithProblems(data, "success", false);
                    else if(data['result'] == "timeout")
                        displayTaskStudentAlertWithProblems(data, "warning", false);
                    else if(data['result'] == "overflow")
                        displayTaskStudentAlertWithProblems(data, "warning", false);
                    else if(data['result'] == "killed")
                        displayTaskStudentAlertWithProblems(data, "warning", false);
                    else // == "error"
                        displayTaskStudentAlertWithProblems(data, "danger", false);

                    if("tests" in data){
                        updateSubmission(submissionid, data['result'], data["grade"], data["tests"]);
                    }else{
                        updateSubmission(submissionid, data['result'], data["grade"], []);
                    }
                    unblurTaskForm();

                    if("replace" in data && data["replace"] && $('#my_submission').length) {
                        displayEvaluatedSubmission(submissionid, true);
                    } else if($('#my_submission').length) {
                        displayEvaluatedSubmission($('#my_submission').attr('data-submission-id'), false);
                    }

                    if("feedback_script" in data)
                        eval(data["feedback_script"]);
                }
                else
                {
                    displayTaskStudentAlertWithProblems(data, "danger", false);
                    updateSubmission(submissionid, "error", "0.0", []);
                    updateTaskStatus("Failed", 0);
                    unblurTaskForm();
                }

            })
            .fail(function()
            {
                displayTaskStudentAlertWithProblems(data, "danger", false);
                updateSubmission(submissionid, "error", "0.0", []);
                updateTaskStatus("Failed", 0);
                unblurTaskForm();
            });
    }, 1000);
}

//Kill a running submission
function killSubmission(submissionid)
{
    $('.kill-submission-btn').attr('disabled', 'disabled');
    var url = $('form#task').attr("action");
    jQuery.post(url, {"@action": "kill", "submissionid": submissionid}, null, "json").done(function()
    {
        $('.kill-submission-btn').removeAttr('disabled');
    }).fail(function()
    {
        $('.kill-submission-btn').removeAttr('disabled');
    });
}

//Displays debug info
function displayDebugInfo(info)
{
    displayDebugInfoRecur(info, $('#task_debug'));
}
function displayDebugInfoRecur(info, box)
{
    var data = $(document.createElement('dl'));
    data.text(" ");
    box.html(data);

    jQuery.each(info, function(index, elem)
    {
        var namebox = $(document.createElement('dt'));
        var content = $(document.createElement('dd'));
        data.append(namebox);
        data.append(content);

        namebox.text(index);
        if(jQuery.isPlainObject(elem))
            displayDebugInfoRecur(elem, content);
        else
            content.text(elem);
    });
}

//Get the code for a "loading" alert, with a button to kill the current submission
function getLoadingAlertCode(title, content, submissionid)
{
    var kill_button = undefined;
    if(submissionid != null)
        kill_button =   "<button type='button' onclick='killSubmission(\""+submissionid+"\")' class='btn btn-danger kill-submission-btn btn-small'>"+
                            "<i class='fa fa-close'></i>"+
                        "</button>";
    return getAlertCode(title, content, "info", false, kill_button);
}

//Displays a loading alert in task form
function displayTaskLoadingAlert(submission_wait_data, submissionid)
{
    var task_alert = $('#task_alert');
    var title = '<i class="fa fa-spinner fa-pulse fa-fw" aria-hidden="true"></i> ';
    var content = "";
    if(submission_wait_data != null)
        content += submission_wait_data["text"];
    task_alert.html(getLoadingAlertCode(title, content, submissionid));
}

//Display informations for remote debugging
function displayRemoteDebug(submissionid, submission_wait_data)
{
    var ssh_host = submission_wait_data["ssh_host"];
    var ssh_port = submission_wait_data["ssh_port"];
    var ssh_user = submission_wait_data["ssh_user"];
    var ssh_password = submission_wait_data["ssh_password"];

    var pre_content = "ssh " + ssh_user + "@" + ssh_host + " -p " + ssh_port+ " -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o PreferredAuthentications=password";
    var task_alert = $('#task_alert');
    var title = '<i class="fa fa-spinner fa-pulse fa-fw" aria-hidden="true"></i> ';
    var content = submission_wait_data["text"];

    //If not already set
    if($('pre#commandssh', task_alert).text() !== pre_content)
    {
        var remote_info = $("#ssh_template").clone();

        $('#commandssh', remote_info).text(pre_content);

        // Generate iframe
        var webtermdiv = $("#webterm", remote_info);
        var webterm_link = $('#webterm_link', remote_info).val();
        if(webterm_link !== undefined)
        {
            var full_link = webterm_link + "?host=" + ssh_host + "&port=" + ssh_port + "&password=" + ssh_password;
            $('<iframe>', {
                src:         full_link,
                id:          'iframessh',
                frameborder: 0,
                scrolling:   'no'
            }).appendTo(webtermdiv);
        }

        task_alert.html(getLoadingAlertCode(title, "<div id='ssh_remote_info'>"+remote_info.html()+"</div>", submissionid));
        $("#ssh_remote_info code", task_alert).text(ssh_password);
        $("#ssh_remote_info", task_alert).show();
    }
}

//Displays a loading input alert in task form
function displayTaskInputLoadingAlert()
{
    var task_alert = $('#task_alert');
    task_alert.html(getAlertCode("<i class=\"fa fa-spinner fa-pulse fa-fw\" aria-hidden=\"true\"></i>", "", "info", false));
    $('html, body').animate(
        {
            scrollTop: task_alert.offset().top - 100
        }, 200);
}

//Displays a loading input alert in task form
function displayTaskInputErrorAlert()
{
    var task_alert = $('#task_alert');
    task_alert.html(getAlertCode("<b>" + $("#internalerror").text() + "</b>", "", "danger", false));
    $('html, body').animate(
        {
            scrollTop: task_alert.offset().top - 100
        }, 200);
}

//Displays a student error alert in task form
function displayTaskStudentAlertWithProblems(content, type)
{
    resetAlerts();

    var firstPos = -1;
    var task_alert = $('#task_alert');

    if("title" in content)
    {
        task_alert.html(getAlertCode(content.title, content.text, type, true));
        firstPos = task_alert.offset().top;
    }

    if("problems" in content)
    {
        for(var problemid in problems_types) {
            if(problemid in content.problems)
                window["load_feedback_" + problems_types[problemid]](problemid, content["problems"][problemid]);
        }
    }

    $('html, body').animate(
    {
        scrollTop: firstPos - 100
    }, 200);

    colorizeStaticCode();
    MathJax.Hub.Queue(["Typeset",MathJax.Hub]);
}

function load_feedback_code(key, content) {
    var alert_type = "danger";
    if(content[0] === "timeout" || content[0] === "overflow")
        alert_type = "warning";
    if(content[0] === "success")
        alert_type = "success";
    $("#task_alert_" + key).html(getAlertCode("", content[1], alert_type, true));
}

function load_feedback_file(key, content) {
    load_feedback_code(key, content);
}

function load_feedback_match(key, content) {
    load_feedback_code(key, content);
}

function load_feedback_code_single_line(key, content) {
    load_feedback_code(key, content);
}

function load_feedback_multiple_choice(key, content) {
    load_feedback_code(key, content);
}

//Create an alert
//type is either alert, info, danger, warning
//dismissible is a boolean
function getAlertCode(title, content, type, dismissible, additionnal_content)
{
    var a = '<div class="card border-' + type + ' mb-3" role="card">';
    a += '<div class="row no-gutters">';

    //Style 1, when there is a title, display it
    if(title !== "") {
        a += '<div class="col">';
        a += '<div class="card-header bg-' + type + ' text-white">';
        if (dismissible)
            a += '<button type="button" class="close" data-dismiss="card" style="color: white;"><span aria-hidden="true">×</span><span class="sr-only">Close</span></button>';
        a += title;
        a += '</div>';
        if (content !== "") {
            a += '<div class="card-body">';
            a += content;
            a += '</div>';
        }
        a += '</div>';
    }
    else {
        //left part
        a += '<div class="col-auto bg-' + type + ' text-white card-left-icon">';
        if(type === "danger") {
            a += '&times;';
        }
        else if(type === "success") {
            a += '&#x2713;';
        }
        else {
            a += '?';
        }
        a += '</div>';

        //right part
        a += '<div class="col">';
        a += '<div class="card-body px-2">';
        if (dismissible)
            a += '<button type="button" class="close" data-dismiss="card"><span aria-hidden="true">×</span><span class="sr-only">Close</span></button>';
        a += content;
        a += '</div>';
        a += '</div>';
    }

    if(additionnal_content !== undefined) {
        a += '<div class="col-auto">';
        a += additionnal_content;
        a += '</div>';
    }

    a += '</div>';
    a += '</div>';
    return a;
}

//Load an old submission input
function loadOldSubmissionInput(id, with_feedback)
{
    if(loadingSomething)
        return;

    blurTaskForm();
    resetAlerts();
    displayTaskInputLoadingAlert();

    var url = $('form#task').attr("action");
    jQuery.post(url, {"@action": "load_submission_input", "submissionid": id}, null, "json")
        .done(function(data)
        {
            if("status" in data && data['status'] == "ok" && "input" in data)
            {
                updateMainTags(data);
                unblurTaskForm();
                load_input(id, data['input']);
                if(with_feedback) // load feedback in second place as it may affect the input
                    loadOldFeedback(data);
            }
            else
            {
                displayTaskInputErrorAlert();
                unblurTaskForm();
            }
        }).fail(function()
        {
            displayTaskInputErrorAlert();
            unblurTaskForm();
        });
}

//Load feedback from an old submission
function loadOldFeedback(data)
{
    if("status" in data && "result" in data)
    {
        if("debug" in data)
            displayDebugInfo(data["debug"]);

        if(data['result'] == "failed")
            displayTaskStudentAlertWithProblems(data, "danger", false);
        else if(data['result'] == "success")
            displayTaskStudentAlertWithProblems(data, "success", false);
        else if(data['result'] == "timeout")
            displayTaskStudentAlertWithProblems(data, "warning", false);
        else if(data['result'] == "overflow")
            displayTaskStudentAlertWithProblems(data, "warning", false);
        else if(data['result'] == "killed")
            displayTaskStudentAlertWithProblems(data, "warning", false);
        else // == "error"
            displayTaskStudentAlertWithProblems(data, "danger", false);
    }
    else
        displayTaskStudentAlertWithProblems($("#internalerror").text(), "danger", false);
    if("feedback_script" in data)
        eval(data["feedback_script"]);
}

//Load data from input into the form inputs
function load_input(submissionid, input)
{
    for(var key in problems_types) {
        window["load_input_" + problems_types[key]](submissionid, key, input);
    }
}

function load_input_code(submissionid, key, input)
{
    if(key in codeEditors) {
        if(key in input)
            codeEditors[key].setValue(input[key], -1);
        else
            codeEditors[key].setValue("", -1);
    }
    else {
        var field = $("input[name='" + key + "']");
        if(key in input)
            $(field).val(input[key]);
        else
            $(field).val("");
    }
}

function load_input_code_single_line(submissionid, key, input)
{
    load_input_code(submissionid, key, input);
}

function load_input_file(submissionid, key, input)
{
    if(key in input) {
        var allowed_exts = $("input[name='" + key + "']").data("allowed-exts");
        var url = $('form#task').attr("action") + "?submissionid=" + submissionid + "&questionid=" + key;
        var input_file = $('#download-input-file-' + key);
        input_file.attr('href', url );
        input_file.css('display', 'block');
        if(allowed_exts.indexOf(".pdf") >= 0) {
            var input_file_pdf = $('#download-input-file-pdf-' + key);
            input_file_pdf.attr('data', url);
            input_file_pdf.find("embed").attr("src", url);
            input_file_pdf.css('display', 'block');
        }
    }
}

function load_input_multiple_choice(submissionid, key, input)
{
    var field = $(".problem input[name='" + key + "']");
    if(key in input)
    {
        if($(field).attr('type') == "checkbox" && jQuery.isArray(input[key])) {
            $(field).each(function () {
                $(this).prop('checked', input[key].indexOf($(this).val()) > -1);
            });
        } else if($(field).attr('type') == "radio") {
            $(field).each(function () {
                $(this).prop('checked', input[key] == $(this).val());
            });
        } else
            $(field).prop('checked', false);
    }
    else
        $(field).prop('checked', false);
}

function load_input_match(submissionid, key, input) {
    var field = $(".problem input[name='" + key + "']");
    if(key in input)
        $(field).prop('value', input[key]);
    else
        $(field).prop('value', "");
}

/*
 * Update tags visual of HTML nodes that represent tags.
 * The choice of the color depends of data present in data["tests"]
 * Tags equals to true are green
 * Tags equals to false are red
 * Missing tags are blue
 */
function updateMainTags(data){

    //Reset all tags to info style (blue) to avoid no-updated colors
    $('span', $('#main_tag_group')).each(function() {
        //If this is a alert-danger class, this is an misconception
        if($(this).attr('class') == "badge alert-danger"){
            $(this).hide();
        }else if($(this).attr('class') == "badge alert-warning"){
            //Remove auto tags
            $(this).remove();
        }else{
            $(this).attr('class', 'badge alert-info');
        }
    });
        
    if("tests" in data){
        for (var tag in data["tests"]){
            //Get and update the color of HTML nodes that represent tags
            var elem = $('#'.concat(tag.replace("*", "\\*"))); //The * makes error with JQuery so, we escape it.
            if(data["tests"][tag]){
                //If this is a alert-danger class, this is an misconception
                if(elem.attr('class') == "badge alert-danger"){
                    elem.show();
                }else{
                    elem.show();
                    elem.attr('class', 'badge alert-success')
                }
            }
            if(tag.startsWith("*auto-tag-")){
                var max_length = 28;
                if(data["tests"][tag].length > max_length){
                    $('#main_tag_group').append('<span class="badge alert-warning" data-toggle="tooltip" data-placement="top" data-original-title="'+data["tests"][tag]+'">'+data["tests"][tag].substring(0, max_length)+'…</span>');
                }
                else{
                    $('#main_tag_group').append('<span class="badge alert-warning">'+data["tests"][tag]+'</span>');
                }
            }
        }
    }
}

/*
 * Update color of tags presents in 'elem' node. 
 * 'data' is a dictionnary that should contains tag values in data["tests"][tag] = True/False
 */
function updateTagsToNewSubmission(elem, data){

    var n_ok = 0;   // number of tag equals true
    var tags_ok = [];
    var n_tot = 0;  // total number of tags
    var badge = elem.find('span[id="tag_counter"]');
    
    //Get all tags listed in main tag section
    $('span', $('#main_tag_group')).each(function() {
        var id = $(this).attr("id");
        if(id in data && data[id]){
            n_ok++;
            tags_ok.push($(this).text());
        }
        n_tot++;
    });
    badge.text(n_ok);
    badge.attr("data-toggle", "tooltip");
    badge.attr("data-placement", "left");
    badge.attr('data-original-title', tags_ok.join(", "));

}

/*
 * Loads the submission form from the local storage
 * and calls the load input functions for each subproblem type
 */
function load_from_storage(courseid,taskid){
    if (typeof(Storage) !== "undefined") {
        var indict = JSON.parse(localStorage[courseid+"/"+taskid]);
        for(var problemid in problems_types) {
            // Submissionid is only used for files that can't be stored here
            // It is set to null here.
            window["load_input_" + problems_types[problemid]](null, problemid, indict);
        }
    } else {
        alert("Your browser doesn't support web storage");
    }
}

/*
 * Saves a serialized version of the form which is typically
 * how the submission input is stored and passed to the load input function.
 */
function save_to_storage(courseid,taskid){
    if (typeof(Storage) !== "undefined") {
        var data = $('form').serializeArray().reduce(function(obj, item) {
            if(item.name in obj)
                // Should be in an array case
                obj[item.name].push(item.value);
            else
                obj[item.name] = Boolean(is_input_list[item.name]) ? [item.value] : item.value;
            return obj;
        }, {});
        localStorage.setItem(courseid+"/"+taskid, JSON.stringify(data));
    } else {
        alert("Your browser doesn't support web storage");
    }
}
