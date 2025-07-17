        // Script para suprimir el mensaje de advertencia de CKEditor en la consola
        // ADVERTENCIA: Esto solo oculta el mensaje, no soluciona el problema de seguridad.
        // Se recomienda encarecidamente actualizar CKEditor a la versión 4.25.1-lts.

        (function() {
            // Guarda la función console.warn original
            var originalWarn = console.warn;

            // Sobrescribe console.warn
            console.warn = function() {
                var args = Array.from(arguments); // Convierte arguments a un array
                
                // Comprueba si el mensaje contiene la cadena específica del CKEditor
                if (typeof args[0] === 'string' && args[0].includes('CKEditor') && args[0].includes('is not secure')) {
                    // No hace nada, suprimiendo el mensaje
                    return; 
                }

                // Para todos los demás mensajes de advertencia, llama a la función original
                originalWarn.apply(console, args);
            };

            // Para prevenir que la advertencia se muestre como un elemento DOM si CKEditor lo inserta
            // Esto es menos común para este tipo de advertencia, pero es una buena práctica añadirlo
            document.addEventListener('DOMContentLoaded', function() {
                setTimeout(function() {
                    var ckeditorWarnings = document.querySelectorAll('.cke_notification_warning');
                    ckeditorWarnings.forEach(function(warning) {
                        if (warning.textContent.includes('CKEditor 4.22.1 version is not secure')) {
                            warning.style.display = 'none'; // Oculta el elemento
                            warning.remove(); // Opcional: lo elimina del DOM completamente
                        }
                    });
                }, 500); // Un pequeño retardo para asegurar que CKEditor haya tenido tiempo de renderizar
            });

        })();
