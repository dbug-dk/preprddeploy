(function ($) {
    $(function () {
        $('.table-expandable').each(function () {
            var table = $(this);
            table.children('thead').children('tr').append('<th></th>');
            table.children('tbody').children('tr').filter(':odd').hide();
            table.children('tbody').children('tr').filter(':even').each(function () {
                var element = $(this);
                element.append('<td style="vertical-align: middle"><div class="table-expandable-arrow"></div></td>');
            });
            table.children('tbody').children('tr').filter(':even').find('.table-expandable-arrow').parent().click(function () {
                var element = $(this).parents('tr');
                console.log(element)
                console.log(element.next('tr'))
                element.next('tr').toggle('slow');
                element.find(".table-expandable-arrow").toggleClass("up");
            });
        });
    });
})(jQuery); 