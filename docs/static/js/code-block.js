/* Behaviour of the "code" shortcode: shell prompt markers, output folding and
   the copy-to-clipboard button.

   This lives in a global script rather than in the shortcode itself because a
   shortcode can be rendered several times for the same page (RSS, summaries),
   so a Page.Scratch "emit once" guard may spend its only chance on a render
   whose output is not the HTML page. */
(function () {
    function applyShellPromptMarkers() {
        var containers = document.querySelectorAll('.shell-prompt-enabled[data-shell-prompt-lines]');

        containers.forEach(function (container) {
            var rawLines = container.getAttribute('data-shell-prompt-lines');
            if (!rawLines) {
                return;
            }

            var lineElements = container.querySelectorAll('.highlight .line');
            if (!lineElements.length) {
                return;
            }

            rawLines.split(',').forEach(function (lineNumberText) {
                var lineNumber = parseInt(lineNumberText, 10);
                if (!lineNumber || lineNumber < 1 || lineNumber > lineElements.length) {
                    return;
                }

                lineElements[lineNumber - 1].classList.add('has-shell-prompt');
            });
        });
    }

    function getCodeText(container) {
        var copyCommandsOnly = container.getAttribute('data-copy-commands-only') === 'true';
        if (copyCommandsOnly) {
            var commandLines = container.querySelectorAll('.highlight .line.has-shell-prompt');
            if (!commandLines.length) {
                return '';
            }

            return Array.prototype.map.call(commandLines, function (lineElement) {
                var contentElement = lineElement.querySelector('.cl');
                return (contentElement ? contentElement.textContent : lineElement.textContent).replace(/\r?\n$/, '');
            }).join('\n');
        }

        var withLineNumbers = container.querySelector('.highlight table td:last-child pre');
        if (withLineNumbers) {
            return withLineNumbers.textContent;
        }

        var codeElement = container.querySelector('.highlight pre code');
        if (codeElement) {
            return codeElement.textContent;
        }

        var preElement = container.querySelector('pre');
        return preElement ? preElement.textContent : '';
    }

    async function copyText(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
            return;
        }

        var textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.setAttribute('readonly', '');
        textarea.style.position = 'absolute';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', applyShellPromptMarkers);
    } else {
        applyShellPromptMarkers();
    }

    document.addEventListener('click', function (event) {
        var toggle = event.target.closest('.toggle-output-button');
        if (!toggle) {
            return;
        }

        var container = document.getElementById(toggle.getAttribute('data-toggle-target'));
        if (!container) {
            return;
        }

        var folded = container.classList.toggle('output-folded');
        toggle.setAttribute('aria-expanded', folded ? 'false' : 'true');

        var toggleLabel = toggle.querySelector('.toggle-output-label');
        if (toggleLabel) {
            toggleLabel.textContent = folded ? 'Show output' : 'Hide output';
        }
    });

    document.addEventListener('click', async function (event) {
        var button = event.target.closest('.copy-code-button');
        if (!button) {
            return;
        }

        var targetId = button.getAttribute('data-copy-target');

        var container = targetId ? document.getElementById(targetId) : null;
        if (!container) {
            console.error('Code block not found for ID:', targetId);
            return;
        }

        var label = button.querySelector('.code-copy-label');
        var originalLabel = label ? label.textContent : 'Copy';

        try {
            await copyText(getCodeText(container));
            button.classList.add('is-copied');
            if (label) {
                label.textContent = 'Copied!';
            }
        } catch (error) {
            console.error('Error while copying:', error);
            if (label) {
                label.textContent = 'Error';
            }
        }

        setTimeout(function () {
            button.classList.remove('is-copied');
            if (label) {
                label.textContent = originalLabel;
            }
        }, 1500);
    });
})();
