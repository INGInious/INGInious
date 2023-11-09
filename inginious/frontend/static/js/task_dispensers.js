//
// This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
// more information about the licensing of this file.
//

var dispenser_deleted_tasks = [];
var dispenser_wiped_tasks = [];
var dispenser_new_tasks = [];
var dragged_from;
var draggable_sections = {};
var draggable_tasks = {};
var timeouts = [],  lastenter;
var warn_before_exit = false;
var dispenser_config = {};

/*****************************
 *     Renaming Elements     *
 *****************************/
function dispenser_util_rename_section(element, new_section) {
    handle = $(element).closest(".handle").removeClass("handle");
    element.hide();

    input = $("<input>").attr({value: element.text().trim(), class: "form-control"}).insertBefore(element);
    input.focus().select();

    quit = function () {
        element.text(input.val()).show();
        input.remove();
        handle.addClass("handle");
        if(new_section) {
            var section = $(element).closest(".section").attr("id","section_"+string_to_id(input.val()));
            draggable_sections[section[0].id] = dispenser_util_make_sections_list_sortable(section);
            draggable_tasks[section[0].id] = dispenser_util_make_tasks_list_sortable(section);
        }
        warn_before_exit = true;
        dispenser_util_update_section_select();
    };

    input.focusout(quit);
    input.keyup(function (e) {
        if (e.keyCode === 13) {
            quit();
        }
    });
}

/**************************
 *  Create a new section  *
 **************************/
function dispenser_util_create_section(parent) {
    const level = Number(parent.attr("data-level"));

    const section = $("#empty_section").clone().show().appendTo(parent.children(".content"));
    parent.children(".config").removeClass("bg-light");
    warn_before_exit = true;
    section.attr("data-level", level + 1);

    dispenser_util_content_modified(parent);
    dispenser_util_rename_section(section.find(".title"), true);
}

/*****************************
 *  Adding task to sections  *
 *****************************/
function dispenser_util_open_task_modal(target) {
    $('#add_existing_tasks').attr('data-target', target.closest('.section').id);
    $('#add_new_task').attr('data-target', target.closest('.section').id);
    $('#new_task_id').attr('data-target', target.closest('.section').id.to_section_id());

    var placed_task = [];
    $('.task').each(function () {
        placed_task.push(this.id.to_taskid());
    });

    $("#modal_task_list .modal_task").filter(function () {
        // remove task already placed in the structure
        const is_placed = placed_task.includes($(this).children("input").val());
        $(this).toggle(!is_placed);
        $(this).toggleClass("disable", is_placed);

        // reset the selection
        $(this).children("input").attr("checked", false);
        $(this).removeClass("bg-primary text-white");
    });

    var no_task_avalaible = $("#modal_task_list .modal_task").not(".disable").length === 0;
    $("#searchTask").val("").toggle(!no_task_avalaible);
    $("#no_task_available").toggle(no_task_avalaible);
}

function dispenser_util_search_task(search_field) {
    var value = $(search_field).val().toLowerCase();
    $("#modal_task_list .modal_task").filter(function () {
        const match_search = $(this).children(".task_name").text().toLowerCase().indexOf(value) > -1;
        const is_unplaced = !$(this).hasClass("disable");
        $(this).toggle(match_search && is_unplaced);
    });
}

function dispenser_util_click_modal_task(task) {
    $(task).toggleClass("bg-primary text-white");
    const input = $(task).find("input");
    input.attr("checked", !input.attr("checked"));
}

function dispenser_util_add_tasks_to_section(button) {
    task_id= $("#new_task_id").val();
    var selected_tasks = [];
    var existing_task = $(button).attr("id") == "add_existing_tasks";
    if(existing_task) {
        $.each($("input[name='task']:checked"), function () {
            selected_tasks.push($(this).val());
        });
    }
    else {
        if(!task_id.match(/^[a-zA-Z0-9_\-]+$/)){
            alert('Task id should only contain alphanumeric characters (in addition to "_" and "-").');
            return;
        }
        selected_tasks.push(task_id);
    }

    const section = $("#" + $(button).attr('data-target'));
    const content = section.children(".content");

    for (var i = 0; i < selected_tasks.length; i++) {
        warn_before_exit = true;
        if(existing_task)
            content.append($("#task_" + selected_tasks[i] + "_clone").clone().attr("id", 'task_' + selected_tasks[i]));
            if(!(selected_tasks[i] in dispenser_config))
                dispenser_config[selected_tasks[i]] = {};
	else {
            // Copy and add the new task
            var new_task_clone = $("#new_task_clone").clone();
            new_task_clone.attr("id", 'task_' + selected_tasks[i]);
            new_task_clone.html(new_task_clone.html().replaceAll("NEWTASKID", selected_tasks[i]));
            new_task_clone.find(".task_settings").tooltip({"placement": "bottom"})
            new_task_clone.find(".delete_task").tooltip({"placement": "bottom"})
            content.append(new_task_clone);

            // Copy and add the new fields
            var new_modal_clone = $("#edit-modals-template").clone();
            new_modal_clone.html(new_modal_clone.html().replaceAll("NEWTASKID", selected_tasks[i]));
            $("#edit-modals").append(new_modal_clone.children(".modal"));
            $("#edit-modals").trigger("new_task");
            dispenser_add_task(selected_tasks[i]);
        }
    }

    dispenser_util_content_modified(section);
}

/*********************
 *  Delete elements  *
 *********************/
function dispenser_util_open_delete_modal(button) {
    if($(button).hasClass("delete_section")) {
        $('#delete_section_modal .submit').attr('data-target', button.closest('.section').id);
        $('#delete_section_modal .wipe_tasks').prop("checked", false);

    } else if($(button).hasClass("delete_task")){
        $('#delete_task_modal .submit').attr('data-target', button.closest('.task').id);
        $('#delete_task_modal .wipe_tasks').prop("checked", false);
    }
}

function dispenser_util_delete_selection(keep_files) {
    $(".grouped-actions-task:checked").each(function () {
        let button = $("#task_" + $(this).data("taskid") + " button.delete_task");
        dispenser_util_delete_task(button, keep_files, $(this).data("taskid"));
    });
}

function dispenser_util_delete_section(button, keep_files) {
    const section = $("#" + button.getAttribute('data-target'));
    const parent = section.parent().closest(".sections_list");
    const wipe = $('#delete_section_modal .wipe_tasks').prop("checked");

    section.find(".task").each(function () {
        const taskid = this.id.to_taskid();
        if(!keep_files){
            $("#modal_task_" + taskid).remove()
            dispenser_delete_task(taskid)
        }
        if(wipe){
            dispenser_wipe_task(taskid)
        }
    });
    section.remove()

    warn_before_exit = true;
    dispenser_util_content_modified(parent);
}

function dispenser_util_delete_task(button, keep_files, taskid){
    $(button).mouseleave().focusout();
    var wipe = false;
    if(!taskid) {
        taskid = button.getAttribute('data-target').to_taskid();
        wipe = $('#delete_task_modal .wipe_tasks').prop("checked");
    }
    if(!keep_files){
        $("#modal_task_" + taskid).remove()
        dispenser_delete_task(taskid)
    }
    if(wipe){
        dispenser_wipe_task(taskid)
    }
    const task = $("#task_" + taskid);
    const parent = task.closest(".tasks_list");
    task.remove();
    delete dispenser_config[taskid];

    warn_before_exit = true;
    dispenser_util_content_modified(parent);
}

/*******************************
 *  Adapt structure to change  *
 *******************************/

function dispenser_toggle_adapt_viewport() {
    let button = $("#compact-view");
    if(button.hasClass("active"))
        button.removeClass("active");
    else
        button.addClass("active");
    dispenser_util_adapt_viewport();
}

function dispenser_util_adapt_viewport() {
    $("#course_structure").removeAttr("style");
    if($("#compact-view").hasClass("active")) {
        var viewport_height = window.innerHeight;
        var document_height = $("#main-content").innerHeight() + $("#inginious-top").innerHeight();
        var overflow = document_height - viewport_height;
        if (overflow > 0) {
            $("#course_structure").height($("#course_structure").height() - overflow);
            $("#course_structure").css("overflow", "auto");
        }
    }
}

function dispenser_util_adapt_size(element) {
    const level = Number($(element).parent().closest(".sections_list").attr("data-level")) + 1;
    $(element).attr("data-level", level);

    const title = $(element).children(".section_header").find(".title");
    if (/h\d/.test(title.attr("class"))) {
        title.attr("class", "title h" + level + " mr-3")
    }

    $(element).children(".content").children(".section").each(function () {
        dispenser_util_adapt_size(this, level + 1)
    });
}


function dispenser_util_content_modified(section) {
    if(section.hasClass("sections_list") && section.hasClass("tasks_list")){
        if(section.children(".content").children(".section").length){
            dispenser_util_empty_to_subsections(section);
            draggable_tasks[section[0].id].option("disabled", true);
        }
        if(section.children(".content").children(".task").length){
            dispenser_util_empty_to_tasks(section);
            draggable_sections[section[0].id].option("disabled", true);
        }
    } else if (section.hasClass("section") && section.children(".content").children().length === 0){
        if(section.hasClass("sections_list")) {
            draggable_tasks[section[0].id] = dispenser_util_make_tasks_list_sortable(section);
        }
        if(section.hasClass("tasks_list")) {
            draggable_sections[section[0].id] = dispenser_util_make_sections_list_sortable(section);
        }
        dispenser_util_section_to_empty(section);
    }
    dispenser_util_update_section_select();
    dispenser_util_adapt_viewport();
}

function dispenser_util_section_to_empty(section) {
    section.addClass("sections_list tasks_list card");
    const header = section.children(".section_header").removeClass("divided").addClass("card-header");
    header.children(".title").attr("class", "title");
    header.children(".divider").hide();

    const text_placeholder = $("#empty_section").find(".section_placeholder").html().trim();
    const para = $("<p>").attr("class", "section_placeholder text-center align-middle m-2").html(text_placeholder);
    section.children(".content").removeClass("ml-4").addClass("list-group list-group-flush").append(para);
}

function dispenser_util_empty_to_subsections(section) {
    const  level = Number($(section).attr("data-level"));

    section.removeClass("tasks_list card");
    const section_header = section.children(".section_header").removeClass("card-header").addClass("divided");
    section_header.children(".title").attr("class", "title h" + level + " mr-3");
    section_header.children(".divider").show();

    section.children(".content").removeClass("list-group list-group-flush").addClass("ml-4").children(".section_placeholder").remove();
}

function dispenser_util_empty_to_tasks(section) {
    section.removeClass("sections_list");
    section.find(".section_placeholder").remove();
}

/*******************/
/* Grouped actions */
/*******************/

function dispenser_util_update_section_select() {
    $("#grouped-actions-section-select").find("option").remove();
    $("#course_structure .section").each(function () {
        let id = this.id;
        let level = $(this).data('level') - 3;
        let title = "-".repeat(level) + " " + $(this).find(".title").first().text().trim();
        let enabled = $(this).hasClass("tasks_list");
        $("#grouped-actions-section-select").append($('<option>', { value: id, text: title, disabled: !enabled}));
    });
}

function dispenser_util_move_selection() {
    let dest = $("#grouped-actions-section-select :selected").val();
    $(".grouped-actions-task:checked").each(function () {
        let elem = $("#task_" + $(this).data("taskid"));
        let source = elem.parent().parent();

        elem.detach().appendTo($("#" + dest + " .list-group"));
        dispenser_util_content_modified(source);
    });
    dispenser_util_content_modified($('#' + dest));
}

/****************************
 *  Drag and drop elements  *
 ****************************/
function dispenser_util_make_tasks_list_sortable(element) {
    return new Sortable(element.children(".content")[0], {
        group: 'tasks_list',
        animation: 150,
        fallbackOnBody: false,
        swapThreshold: 0.1,
        dragoverBubble: true,
        handle: ".handle",
        onStart: function (evt) {
            dragged_from = evt.from;

            // open sections when exo hover it for more than 0.7s
            $('.tasks_list').children('.section_header').on({
                dragenter: function(event){
                    const list = $(this).closest(".section").children('.content');
                    lastenter = event.target;
                    timeouts.push(setTimeout(function(){
                        list.slideDown('fast');
                    }, 700));

                },
                dragleave: function(event){
                    // dragleave is fired when hover child
                    if(event.target == lastenter) {
                        for (var i=0; i<timeouts.length; i++) {
                          clearTimeout(timeouts[i]);
                        }
                    }
                }});
        },
        onChange: function (evt) {
            dispenser_util_content_modified($(dragged_from).closest(".section"));
            dispenser_util_content_modified($(evt.to).closest(".section"));

            $('.tasks_list').children('.content').each(function(){
                if(this != evt.to ){
                    $(this).slideUp('fast');
                }
            });

            dragged_from = evt.to;
        },
        onEnd: function (evt) {
            $('.tasks_list').children('.content').slideDown('fast');
            $('.tasks_list').children('.section_header').off('dragenter').off('dragleave');
            warn_before_exit = true;
            evt.to.parentElement.scrollIntoView();
        },
    });
}


function dispenser_util_make_sections_list_sortable(element) {
    return new Sortable(element.children(".content")[0], {
        group: 'sections_list',
        animation: 150,
        fallbackOnBody: false,
        swapThreshold: 0.1,
        dragoverBubble: true,
        handle: ".handle",
        onStart: function (evt) {
            $(evt.item).children('.content').slideUp('fast');
            $('.tasks_list').not('.sections_list').children('.content').slideUp('fast');
            dragged_from = evt.from;
        },
        onEnd: function (evt) {
            $(evt.item).children('.content').slideDown('fast');
            $('.tasks_list').children('.content').slideDown('fast');
            warn_before_exit = true;
            evt.item.scrollIntoView();
        },
        onChange: function (evt) {
            dispenser_util_adapt_size(evt.item);
            dispenser_util_content_modified($(dragged_from).closest(".section"));
            dispenser_util_content_modified($(evt.to).closest(".section"));

            dragged_from = evt.to;
        }
    });
}


/**********************
 *  Submit structure  *
 **********************/

function dispenser_util_get_sections_list(element) {
    return element.children(".section").map(function (index) {
        const structure = {
            "title": $(this).find(".title").first().text().trim(),
        };

        const config = $(this).children(".config");
        if (config.length) {
            structure["config"] = dispenser_util_get_section_config(config);
        }

        const content = $(this).children(".content");
        if ($(this).hasClass("tasks_list")) {
            tasks_id = dispenser_util_get_tasks_list(content);
            structure["tasks_list"] = tasks_id;

        } else if ($(this).hasClass("sections_list")) {
            structure["sections_list"] = dispenser_util_get_sections_list(content);
        }

        return structure;
    }).get();
}

function dispenser_util_get_section_config(element) {
    const config_list = {};
    element.find(".section-config-item").each(function (index) {
        if($(this).attr("type") == "checkbox")
            config_list[this.id] =$(this).is(":checked");
        else
            config_list[this.id] = this.value;
    });
    return config_list;
}

function dispenser_util_get_tasks_list(element) {
    const tasks_list = [];
    element.children(".task").each(function () {
        tasks_list.push(this.id.to_taskid());
    });
    return tasks_list;
}

function dispenser_delete_task(taskid) {
    dispenser_deleted_tasks.push(taskid);
}

function dispenser_wipe_task(taskid) {
    dispenser_wiped_tasks.push(taskid);
}

function dispenser_add_task(taskid) {
    if(!taskid.match(/^[a-zA-Z0-9_\-]+$/)){
        alert('Task id should only contain alphanumeric characters (in addition to "_" and "-").');
        return;
    }
    dispenser_new_tasks.push(taskid);
}

function dispenser_util_get_task_config() {
    let tasks_config = {};
    dispenser_util_get_tasks_list($('#course_structure .content')).forEach(function (elem) {
        tasks_config[elem] = {};
    });

    for(const config_func of task_config_funcs) {
        config_func(tasks_config);
    }

    return tasks_config;
}

function dispenser_util_structure() {
    return JSON.stringify({
        "toc": dispenser_util_get_sections_list($('#course_structure').children(".content")),
        "config": dispenser_config
    });
}

function dispenser_structure_toc() {
    return dispenser_util_structure();
}

function dispenser_structure_combinatory_test() {
    return dispenser_util_structure();
}

function dispenser_submit(dispenser_id) {
    var structure_json = window['dispenser_structure_' + dispenser_id]();
    warn_before_exit = false;
    $("<form>").attr("method", "post").appendTo($("#dispenser_data")).hide()
        .append($("<input>").attr("name", "course_structure").val(structure_json))
        .append($("<input>").attr("name", "new_tasks").val(JSON.stringify(dispenser_new_tasks)))
        .append($("<input>").attr("name", "deleted_tasks").val(JSON.stringify(dispenser_deleted_tasks)))
        .append($("<input>").attr("name", "wiped_tasks").val(JSON.stringify(dispenser_wiped_tasks))).submit();
}

/************************
 *  String manipulation  *
 ************************/
function string_to_id(string) {
    var ID = string.toLowerCase().replace(/\s/g, '_');
    ID = ID.replace(/\W/g, '');
    ID = ID.replace(/_+/g, '_');

    if ($("#section_" + ID).length) {
        for (i = 1; $("#section_" + ID + "_" + i).length; i++) {
        }
        ID = ID + "_" + i;
    }
    return ID ;
}

String.prototype.to_taskid = function () {
    return this.slice(5);
};
String.prototype.to_section_id = function () {
    return this.slice(8);
};

/************************
 *   Warn before exit   *
 ************************/
$(window).bind('beforeunload', function(){
    if(warn_before_exit){
        return 'All change will be lost! Are you sure you want to leave?';
    } else {
        return undefined;
    }
});
