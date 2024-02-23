//
// This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
// more information about the licensing of this file.
//
"use strict";

function init_common()
{
    //Init CodeMirror
    colorizeStaticCode();
    $('.code-editor').each(function(index, elem)
    {
        registerCodeEditor(elem, $(elem).attr('data-x-language'), $(elem).attr('data-x-lines'), $(elem).attr('data-x-first-line'));
    });

    //Fix a bug with codemirror and bootstrap tabs
    $('a[data-toggle="tab"]').on('shown.bs.tab', function(e)
    {
        var target = $(e.target).attr("href");
        $(target + ' .CodeMirror').each(function(i, el)
        {
            el.CodeMirror.refresh();
        });
    });

    //Enable tooltips
    $(function()
    {
        //Fix for button groups
        var all_needed_tooltips = $('[data-toggle="tooltip"]');
        var all_exceptions = $('.btn-group .btn[data-toggle="tooltip"], td[data-toggle="tooltip"]');

        var not_exceptions = all_needed_tooltips.not(all_exceptions);

        not_exceptions.tooltip();
        all_exceptions.tooltip({'container': 'body'});
    });
}

//Contains all code editors
var codeEditors = {};

//Run CodeMirror on static code
function colorizeStaticCode()
{
    $('.code.literal-block').each(function()
    {
        var classes = $(this).attr('class').split(' ');
        var mode = undefined;
        $.each(classes, function(idx, elem)
        {
            if(elem != "code" && elem != "literal-block")
            {
                var nmode = CodeMirror.findModeByName(elem);
                if(nmode != undefined)
                    mode = nmode;
            }
        });
        if(mode != undefined)
        {
            var elem = this;

            CodeMirror.requireMode(mode['mode'], function()
            {
                CodeMirror.colorize($(elem), mode["mime"]);
            });
        }
    });
}

//Register and init a code editor (ace)
function registerCodeEditor(textarea, lang, lines, firstline=1)
{
    var mode = CodeMirror.findModeByName(lang);
    if(mode == undefined)
        mode = {"mode": "plain", "mime": "text/plain"};

    var is_single = $(textarea).hasClass('single');

     var keyMappings = {
        'Ctrl-Enter': function() {
                                 $('body,html').animate({
                                   scrollTop: $('#task-submit').offset().top
                                 }, 'fast');
                               }
     }

    if (user_indentation_type["text"] == "tabs") {
        keyMappings["Tab"] = function(cm) { cm.execCommand("insertTab"); cm.execCommand("indentLess"); cm.execCommand("insertTab"); };
    } else {
        keyMappings["Tab"] = function(cm) { cm.execCommand("insertSoftTab");};
    }



    var editor = CodeMirror.fromTextArea(textarea, {
        lineNumbers:       true,
        firstLineNumber:   parseInt(firstline),
        mode:              mode["mime"],
        foldGutter:        true,
        styleActiveLine:   true,
        matchBrackets:     true,
        autoCloseBrackets: true,
        lineWrapping:      true,
        gutters:           ["CodeMirror-linenumbers", "CodeMirror-foldgutter"],
        indentUnit:        user_indentation_type["indent"],
        indentWithTabs:    user_indentation_type["indentWithTabs"],
        tabSize:           user_indentation_type["indent"],
        viewportMargin:    Infinity,
        lint:              function()
                           {
                               return []
                           },
        extraKeys:         keyMappings
    });

    if(is_single)
        $(editor.getWrapperElement()).addClass('single');

    editor.on("change", function(cm)
    {
        cm.save();
    });

    var min_editor_height = (21 * lines);
    editor.on("viewportChange", function(cm) { onEditorViewportChange(min_editor_height, cm); });
    editor.setSize(null, min_editor_height + "px");
    onEditorViewportChange(min_editor_height, editor); //immediately trigger a size update

    if(mode["mode"] != "plain")
        CodeMirror.autoLoadMode(editor, mode["mode"]);

    codeEditors[$(textarea).attr("name")] =  editor;
    return editor;
}

// Verify if the size of each code editor is sufficient
function onEditorViewportChange(min_editor_height, cm)
{
    if(cm.getScrollInfo()["height"] > min_editor_height)
        cm.setSize(null, "auto");
    else
        cm.setSize(null, min_editor_height + "px");
}

// Apply parent function recursively
jQuery.fn.extend({
    rparent: function (number) {
        if(number==1)
            return $(this).parent();
        else
            return $(this).parent().rparent(number-1);
    }
});

/**
 * Select/deselect all the checkboxes of a panel
 * @param select: boolean indicating if we should select or deselect
 * @param panel_member: a child of the panel in which is the list
 */
function download_page_select(select, panel_member)
{
    panel_member = $(panel_member);
    while(!panel_member.hasClass('card'))
        panel_member = panel_member.parent();
    $('input[type="checkbox"]', panel_member).prop('checked', select);
    $('input[type="checkbox"]', panel_member).trigger('change');
}

/**
 * Select/deselect all the checkboxes of the active panel
 * @param select: boolean indicating if we should select or deselect
 * @param panel_member: a child of the panel in which is the list
 */
function download_page_select_active(select, panel_member)
{
    panel_member = $(panel_member).closest('.card').find(".tab-content .active");
    $('input[type="checkbox"]', panel_member).prop('checked', select).change();
}

/**
 * Select/deselect all the checkboxes of the panel depending on a list of users and groups tutored.
 * @param panel_member: a child of the panel in which is the list
 * @param users: a list of usernames
 * @param audiences: a list of audiences ids
 */
function download_page_select_tutor(panel_member, users, audiences)
{
    panel_member = $(panel_member).closest('.card').find(".tab-content .active");
    $('input[name="audiences"]', panel_member).each(function() { $(this).prop('checked', $.inArray($(this).val(),audiences) != -1); }).trigger('change');
    $('input[name="users"]', panel_member).each(function() { $(this).prop('checked', $.inArray($(this).val(), users) != -1); }).trigger('change');
}

/**
 * Show and hide the section when click on dropdown button
 * @param header: the header on which we click
 */
function dropdown(header) {
    const content_div = $(header).closest(".section").children(".content");
    const button = $(header).children(".dropdown_button")

    if ($(button).hasClass("fa-caret-down")) {
        $(button).removeClass("fa-caret-down").addClass("fa-caret-left");
        content_div.slideUp('fast')
    } else {
        $(button).removeClass("fa-caret-left").addClass("fa-caret-down");
        content_div.slideDown('fast')
    }
}
