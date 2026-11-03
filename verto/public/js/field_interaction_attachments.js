/* Multiple private attachments for new Field Interaction Web Form responses. */
(() => {
    const PAYLOAD_KEY = '_verto_attachments';
    const translate = message => typeof __ === 'function' ? __(message) : message;
    const sizeLabel = bytes => `${Number((bytes / 1048576).toFixed(1))} MB`;

    function element(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    class AttachmentPicker {
        constructor(form, parent) {
            this.form = form;
            this.files = [];
            this.pending = false;
            this.options = null;
            this.root = element('section', 'verto-web-form-attachments mt-4');
            this.root.append(element('h5', '', translate('Attachments')));
            this.help = element('p', 'text-muted small', translate('Loading attachment options…'));
            this.button = element('button', 'btn btn-default btn-sm', translate('Add attachments'));
            this.button.type = 'button';
            this.button.disabled = true;
            this.input = element('input');
            this.input.type = 'file';
            this.input.multiple = true;
            this.input.hidden = true;
            this.input.setAttribute('aria-label', translate('Select attachments'));
            this.status = element('p', 'text-muted small mt-2');
            this.status.setAttribute('aria-live', 'polite');
            this.list = element('ul', 'list-unstyled mt-3');
            this.root.append(this.help, this.button, this.input, this.status, this.list);
            parent.append(this.root);
            this.button.addEventListener('click', () => this.input.click());
            this.input.addEventListener('change', () => {
                const files = Array.from(this.input.files || []);
                this.input.value = '';
                void this.addFiles(files);
            });

            const save = form.save;
            const picker = this;
            form.save = function (...args) {
                if (picker.pending) {
                    frappe.msgprint(translate('Please wait for the selected files to finish loading.'));
                    return false;
                }
                if (picker.files.length) {
                    this.doc[PAYLOAD_KEY] = picker.files.map(({ file_name, content }) => ({ file_name, content }));
                } else {
                    delete this.doc[PAYLOAD_KEY];
                }
                return save.apply(this, args);
            };
            form.events.on('after_save', () => this.clear());

            frappe.call({
                method: 'verto.api.web_form_attachments.get_upload_options',
                args: { web_form: form.name, web_form_request_key: form.web_form_request_key },
            }).then(response => {
                this.options = response.message;
                this.input.accept = this.options.allowed_extensions.map(extension => `.${extension}`).join(',');
                this.help.textContent = `${translate('Select photos or documents.')} ` +
                    `${translate('Files are uploaded when you submit the form.')} ` +
                    `${translate('Maximum files:')} ${this.options.max_files}. ` +
                    `${translate('Per file:')} ${sizeLabel(this.options.max_file_bytes)}. ` +
                    `${translate('Total:')} ${sizeLabel(this.options.max_total_bytes)}.`;
                if (!this.options.allowed_extensions.length) {
                    this.help.textContent = translate('Attachment uploads are unavailable. Contact your site administrator.');
                }
                this.render();
            }).catch(() => {
                this.help.textContent = translate('Attachment uploads are unavailable. Contact your site administrator.');
            });
        }

        async addFiles(files) {
            if (!files.length || !this.options || this.pending || window.saving) return;
            this.pending = true;
            this.render();
            try {
                if (this.files.length + files.length > this.options.max_files) {
                    throw new Error(translate('Too many attachments. Remove a file before adding more.'));
                }
                let total = this.files.reduce((sum, file) => sum + file.size, 0);
                for (const file of files) {
                    const extension = /\.([^.]+)$/.exec(file.name)?.[1].toLowerCase() || '';
                    if (!this.options.allowed_extensions.includes(extension)) {
                        throw new Error(translate('This attachment file type is not allowed.'));
                    }
                    if (!file.size || file.size > this.options.max_file_bytes) {
                        throw new Error(translate('An attachment is empty or exceeds the allowed file size.'));
                    }
                    total += file.size;
                }
                if (total > this.options.max_total_bytes) {
                    throw new Error(translate('The attachments exceed the total upload size limit.'));
                }
                // Read the complete selection before changing the queue, so a read
                // error leaves the visitor's previously selected files intact.
                const additions = await Promise.all(files.map(file => this.readFile(file)));
                this.files.push(...additions);
                this.form.make_form_dirty();
            } catch (error) {
                frappe.msgprint(error.message || translate('Unable to read the selected files. Please try again.'));
            } finally {
                this.pending = false;
                this.render();
            }
        }

        readFile(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onerror = reader.onabort = () => reject(new Error(translate('Unable to read a selected file. Please try again.')));
                reader.onload = () => resolve({
                    file_name: file.name,
                    content: String(reader.result).split(',')[1],
                    size: file.size,
                    preview: /^image\/(jpeg|png|gif)$/.test(file.type) ? String(reader.result) : null,
                });
                reader.readAsDataURL(file);
            });
        }

        render() {
            this.button.disabled = this.pending || !this.options || !this.options.allowed_extensions.length ||
                this.files.length >= this.options.max_files;
            this.status.textContent = this.pending ? translate('Reading selected files…') :
                `${this.files.length} ${translate('files selected')}`;
            this.list.replaceChildren();
            this.files.forEach((file, index) => {
                const row = element('li', 'd-flex align-items-center mb-2');
                row.style.gap = '12px';
                if (file.preview) {
                    const preview = element('img', 'rounded');
                    preview.src = file.preview;
                    preview.alt = '';
                    preview.width = 56;
                    preview.height = 56;
                    preview.style.objectFit = 'cover';
                    row.append(preview);
                }
                const label = element('span', 'small', `${file.file_name} (${sizeLabel(file.size)})`);
                label.style.overflowWrap = 'anywhere';
                label.style.minWidth = '0';
                label.style.flex = '1';
                const remove = element('button', 'btn btn-default btn-xs', translate('Remove'));
                remove.type = 'button';
                remove.disabled = this.pending;
                remove.setAttribute('aria-label', `${translate('Remove')} ${file.file_name}`);
                remove.addEventListener('click', () => {
                    if (this.pending || window.saving) return;
                    this.files.splice(index, 1);
                    this.form.make_form_dirty();
                    this.render();
                });
                row.append(label, remove);
                this.list.append(row);
            });
        }

        clear() {
            this.files = [];
            delete this.form.doc[PAYLOAD_KEY];
            this.render();
        }
    }

    function setup() {
        const form = frappe.web_form;
        const parent = document.querySelector('.web-form-body');
        if (!parent || !form || form.doc_type !== 'Field Interaction' || !form.is_new ||
            form.is_list || form.doc?.name || form._vertoAttachments) return;
        form._vertoAttachments = new AttachmentPicker(form, parent);
    }

    // Website scripts can load before the Web Form ready callback. Run after
    // all synchronous ready callbacks without replacing the site's client script.
    frappe.ready(() => setTimeout(setup, 0));
})();
