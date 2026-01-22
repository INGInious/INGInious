//Various functions to display remaining times
$(function()
{
	$('.contest_starting_time').each(contest_starting_time);
	$('.contest_remaining_time').each(contest_remaining_time);
	$('.contest_blackout_time').each(contest_blackout_time);
});

function contest_starting_time()
{
	$(this).countdown(new Date($(this).attr('starts-at'))).on('update.countdown', function(event)
	{
		var format = '%H:%M:%S';
		if(event.offset.totalDays > 0) {
			format = '%-D day%!D ' + format;
		}
		$(this).html("Contest starts in: "+event.strftime(format));
	}).on('finish.countdown', function(event)
	{
		location.reload(); //reload the page
		$(this).html('<b>Contest started!</b>');
	});
}

function contest_remaining_time()
{
	$(this).countdown(new Date($(this).attr('ends-at'))).on('update.countdown', function(event)
	{
		var format = '%H:%M:%S';
		if(event.offset.totalDays > 0) {
			format = '%-D day%!D ' + format;
		}
		$(this).html("Time remaining: "+event.strftime(format));
	}).on('finish.countdown', function(event)
	{
		$(this).html('<b>Contest ended!</b>');
	});
}

function contest_blackout_time()
{
	$(this).countdown(new Date($(this).attr('blackout-at'))).on('update.countdown', function(event)
	{
		var format = '%H:%M:%S';
		if(event.offset.totalDays > 0) {
			format = '%-D day%!D ' + format;
		}
		$(this).html("Blackout in "+event.strftime(format));
	}).on('finish.countdown', function(event)
	{
		$(this).html('<b>Blackout</b>');
	});
}

function dispenser_structure_contest() {
	var course_structure = dispenser_util_structure()
	course_structure['settings'] = {}

    $("#task_dispenser_settings_form input").each(function () {
        course_structure['settings'][$(this).attr("name")] = $(this).is(":checkbox") ? $(this).is(":checked") : $(this).val();
    });

    return JSON.stringify(course_structure);
}