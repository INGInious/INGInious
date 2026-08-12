//
// This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
// more information about the licensing of this file.
//
function revoke_binding(event){
    var username = $(this).data("username");
    var binding_id = $(this).data("binding");
    $.post({
      url: "user_action",
      data: {
        "username":username,
        "action":"revoke_binding",
        "binding_id": binding_id
      },
    }).done(function(feedback) {
        if (!feedback.hasOwnProperty('error')){
            window.location.href = "users";
        }else{
            $('#feedback_bindings').text(feedback['message']);
            $('#feedback_bindings').show();
        }
    });
}
function get_bindings(username){
    var bindings = {};
    $.post({
      async: false,
      url: "user_action",
      data: {
        "username":username,
        "action":"get_bindings",
      },
    }).done(function(result) {
        bindings = result;
    });
    return bindings;
}
function display_bindings(username,bindings){
    for (var elem in bindings) {
        var template = $('#hidden-template').clone();
        template = $(template).children("div.card.mb-3").first().attr('id',elem+'-template').parent().html();
        $("#binding_content").append(template);
        $("#"+elem+"-template .binding_revoke").data("username",username);
        $("#"+elem+"-template .binding_revoke").data("binding",elem);
        $("#"+elem+"-template .binding_identifier").text(bindings[elem][0]);
        $("#"+elem+"-template .binding_method").text(elem);
    }
    $('.binding_revoke').bind("click", revoke_binding);
}

function action_handler(action){
    var username=$('#username').val();
    var realname = "";
    var email = "";
    var password = "";
    if (action == "add_user"){
        username = $('input[name="usrname"]').val();
        realname = $('input[name="realname"]').val();
        email = $('input[name="email"]').val();
        password = $('input[name="password"]').val();
    }
    $.post({
      url: "user_action",
      data: {
        "username":username,
        "realname":realname,
        "email": email,
        "password":password,
        "action":action
      },
    }).done(function(feedback) {
        if (!feedback.hasOwnProperty('error')){
            window.location.href = "users";
        }else{
            $('#feedback').text(feedback['message']);
            $('#feedback').show();
        }
    });
}

function lti_secret_add(deployment_str) {
    if (!deployment_str)
        return;

    // generate secret
    let new_secret = crypto.randomUUID().replace(/-/g, '');

    // fetch client and deploy_id and remove option
    let option = $("option[value='" + deployment_str + "']");
    let client_id = option.data("client-id");
    let deploy_id = option.data("deployment-id");
    option.remove();

    // append a new <li> with the secret
    let ul = $("ul[data-client-id='" + client_id + "']");
    let new_li = ul.find("li").first().clone();
    new_li.attr("id", deployment_str);
    new_li.find("span").text(deploy_id);
    new_li.find("code").text(new_secret);
    new_li.data("client-id", client_id);
    new_li.data("deployment-id", deploy_id);
    new_li.find("a").click(function(){ lti_secret_remove(deployment_str); })
    new_li.removeAttr("style");
    new_li.appendTo(ul);

    // apply change to lti_secrets input
    let lti_secrets = $("input[name='lti_secrets']").val();
    $("input[name='lti_secrets']").val(lti_secrets + deployment_str + "/" + new_secret + "\n");
}

function lti_secret_remove(deployment_str) {
    // fetch client and deploy id and remove the <li>
    let secret_li = $("li[id='" + deployment_str+"']");
    let client_id = secret_li.data("client-id");
    let deploy_id = secret_li.data("deployment-id");
    secret_li.remove();

    // append a new option to the select
    let option = jQuery("<option/>", { value: deployment_str, text: deploy_id});
    option.data("client-id", client_id);
    option.data("deployment-id", deploy_id);
    $("select[id='" + client_id + "']").append(option);

    // apply change to lti_secrets input
    let lti_secrets = $("input[name='lti_secrets']").val();
    $("input[name='lti_secrets']").val(lti_secrets
        .split("\n")
        .filter(ligne => !ligne.startsWith(deployment_str))
        .join("\n")
    );
}