//
// This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
// more information about the licensing of this file.
//
"use strict";

let dtf;

$(function()
{
    init_common();
    
    init_webapp();
});

function init_webapp()
{
    //Start affix only if there the height of the sidebar is less than the height of the content
    if($('#sidebar').height() < $('#content').height())
    {
        var start_affix = function() { $('#sidebar_affix').affix({offset: {top: 65, bottom: 61}}); };
        var update_size = function() { $('#sidebar_affix').width($('#sidebar').width()); };
        $(window).scroll(update_size);
        $(window).resize(update_size);
        update_size();
        start_affix();
    }

    $("time").each(function () {
        $(this).text(dtf.format(new Date($(this).attr("datetime"))));
    })
}