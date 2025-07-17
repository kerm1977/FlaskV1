// static/js/timezone_converter.js
document.addEventListener('DOMContentLoaded', function() {
    const datetimeElements = document.querySelectorAll('.utc-datetime');

    datetimeElements.forEach(element => {
        const utcDateTimeString = element.getAttribute('data-utc');

        if (utcDateTimeString) {
            try {
                const date = new Date(utcDateTimeString);

                const options = {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: false,
                    timeZoneName: 'shortOffset'
                };

                const localDateTime = date.toLocaleString(navigator.language, options);
                element.textContent = localDateTime;
            } catch (e) {
                console.error('Error al parsear o formatear la fecha UTC:', utcDateTimeString, e);
            }
        }
    });
});