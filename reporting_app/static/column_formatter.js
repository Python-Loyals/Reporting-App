
function render_data(data, fmt) {
    if (!data) {
        return null;
    }
    if (!fmt) {
        return data;
    }
    var formatted_data = data;

    if (fmt['type'] == 'percentage') {
        formatted_data = Humanize.toFixed(formatted_data, 1) + '%';
    } else if (fmt['type'] == 'largeint') {
        formatted_data = Humanize.intComma(formatted_data);
    } else if (fmt['type'] == 'largefloat') {
        formatted_data = Humanize.formatNumber(formatted_data, 2);
    }

    if (fmt['link']) {
        formatted_data = '<a href=' + fmt['link'] + data + '>' + formatted_data + '</a>'
    }
    if (fmt['min'] && data < fmt['min']) {
        formatted_data = '<p style="color:red">' + formatted_data + '</p>';
    }

    return formatted_data;
}

