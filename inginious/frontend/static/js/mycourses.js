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
    var classes = ["btn-light", "btn-success", "btn-danger"];
    var old_class = $(this).attr("class").split(' ').filter(element => classes.includes(element));

    if (old_class == "btn-light") {
        $(this).removeClass("btn-light");
        $(this).addClass("btn-success");
        $(this).data("value", "true");
    } else if (old_class == "btn-success") {
        $(this).removeClass("btn-success");
        $(this).addClass("btn-danger");
        $(this).data("value", "false");
    } else if (old_class == "btn-danger") {
        $(this).removeClass("btn-danger");
        $(this).addClass("btn-light");
        $(this).data("value", "null");
    }
}


function search_course(open_courses, pinned_courses){
    // search
    var value = $("#course_search").val().toLowerCase();

    // filter
    var filter_values = Object({"is_archive": null, "is_lti": null, "is_hidden": null, "is_exam": null, "is_pinned": null});
    $(".course_filter").each(function() {
        filter_values[$(this).attr("id")] = eval($(this).data("value"));
    });

    var filtered_courses = [];
    var is_temp_pinned;
    var is_temp_unpinned;
    var is_pinned;

    for (const [courseid, course] of Object.entries(open_courses)) {
        filtered_courses.push(courseid);
        is_temp_pinned = $(document).find('.course_item[data-course-id='+courseid+']').hasClass("temp_pin")
        is_temp_unpinned = $(document).find('.course_item[data-course-id='+courseid+']').hasClass("temp_unpin")

        if (is_temp_pinned) {
            is_pinned = true;
        }
        else if (is_temp_unpinned) {
            is_pinned = false;
        }
        else {
            is_pinned =  pinned_courses.includes(courseid) ? true : false ;
        }

        var course_values = Object({"is_archive": course.is_archive,
                                     "is_lti": course.is_lti,
                                     "is_hidden": course.is_open_to_non_staff,
                                     "is_pinned": is_pinned
                                     });

        for (var filter of Object.keys(course_values)) {
            if (filter_values[filter] === null) {
                continue;
            }
            else if (filter_values[filter] !== course_values[filter]) {
                filtered_courses.pop();
                break;
            }
        }
    }

    //show/hide courses
    $(".course_list .course_item").filter(function() {
        $(this).toggle(($.inArray($(this).data("course-id"), filtered_courses) > -1)
                        && $(this).find(".course_name").text().toLowerCase().indexOf(value) > -1)
    });
}




