//
// This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
// more information about the licensing of this file.
//
"use strict";


function course_pin(event){

    event.preventDefault(); // prevent redirect by <a> tag

    var click_button = $(this);
    var courseid = click_button.data("course-id");

    $.ajax({
        type: "POST",
        url: "/mycourses",
        data: `pinning_courseid=${courseid}`,
        success: function(data) {
            if (!data || data.error) {
                $(".max_pin_alert")
                    .removeClass("d-none")      // make it visible
                    .show()               // ensure jQuery knows it's visible -> needed
                    .delay(3000)
                    .fadeOut(300, function() {
                        $(this).addClass("d-none");
                  });
                 return;
            }

            if (click_button.find("i").hasClass("fa-star-o")) { // pinning

                click_button.find("i").removeClass("fa-star-o").addClass("fa-star text-warning");

                const pinnedItem = `
                    <div class="col mb-4" id="pinned-${courseid}">
                        <div class="card m-2">
                            <div class="card-body course_card">
                                <h5 class="card-title">
                                    <a ${data["is_lti"] && data["lti_url"] ? `target="_blank" href=${data["lti_url"]}` : `href=${data["path"]}`}>
                                        ${data["name"]}
                                    </a>
                                </h5>
                                <div class="card-text card-trunc">
                                    ${data["description"]}
                                </div>
                            </div>
                        </div>
                    </div>`;

                $(document).find("#pinned_list").append(pinnedItem);

                if( $(document).find(".course_card").length > 0) {
                    $(document).find("#no_pin_message").addClass("d-none");
                }
                $(document).find(`.course_item[data-course-id=${courseid}]`).addClass("temp_pin").removeClass("temp_unpin");

            } else { // unpinning
                click_button.find("i").removeClass("fa-star text-warning").addClass("fa-star-o");

                $(document).find(`#pinned-${courseid}`).remove();
                $(document).find(`.course_item[data-course-id=${courseid}]`).removeClass("temp_pin").addClass("temp_unpin");

                if( $(document).find(".course_card").length < 1) {
                    $(document).find("#no_pin_message").removeClass("d-none");
                }
            }
        },
        error: function(data) {
            $(".pin_alert")
                .removeClass("d-none")      // make it visible
                .show()               // ensure jQuery knows it's visible -> needed
                .delay(3000)
                .fadeOut(300, function() {
                    $(this).addClass("d-none");
            });
        }
    });
}


function change_button_color(){
    // change button color

    const classes = ["btn-light", "btn-success", "btn-danger"];
    const values = { "btn-light": "null", "btn-success": "true", "btn-danger": "false" };
    const old_class = classes.find(cls => $(this).hasClass(cls));

    if (old_class) {
        const next_class = classes[(classes.indexOf(old_class) + 1) % classes.length];
        $(this).removeClass(old_class).addClass(next_class);

        $(this).data("value", values[next_class]);
    }
}


function search_course(){
    // search

    $(".course_list .course_item").each(function () {
    var $item = $(this);
    var visible = true;

    $(".course_filter").each(function () {
        var filter_id = this.id;
        var filter_value = eval($(this).data("value"));

        if (filter_value === true && !$item.hasClass(filter_id)) {
            visible = false;
        }
        if (filter_value === false && $item.hasClass(filter_id)) {
            visible = false;
        }
    });

    var search_value = $("#course_search").val().toLowerCase();
    if ($item.find(".course_name").text().toLowerCase().indexOf(search_value) === -1) {
        visible = false;
    }

    $item.toggle(visible);
});
}




