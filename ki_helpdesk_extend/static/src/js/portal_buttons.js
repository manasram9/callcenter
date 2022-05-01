odoo.define('ki_helpdesk_extend.helpdesk', function (require) {
    "use strict";
    require('web.dom_ready');
    var ajax = require('web.ajax');

    $(document).ready(function() {

        $("#email_input_search_1").on("change", function(ev){
            var email = $(ev.target).val();
            $("#email_input_search_2").val(email)
        });

        $("#helpdesk_team_select_id").on("change", function(ev) {
            var team_id = $(ev.target).val();
            if (team_id) {
                ajax.jsonRpc('/ticket/helpdesk_team/validate', 'call', {'team_id': team_id})
                .then(function (result) {
                    $("#helpdesk_team_user_id").empty();
                    for (var i = 0; i < result.length; i++) {
                        $("#helpdesk_team_user_id")[0].appendChild(new Option(result[i]['name'], result[i]['id']));
                    }
                })
                .fail(function () {
                    $("#helpdesk_team_user_id").empty();
                });
            }
            else {
                $("#helpdesk_team_user_id").empty();
            }
        });

        $("#helpdesk_team_select_id").trigger('change');
    });
})