/**
 * SciLit Upload-Seite Skript
 * Enthält Funktionen für die Dokumenten-Upload-Seite
 */

// Sofort ausgeführte Funktion, um den globalen Namespace nicht zu verschmutzen
(function() {
    'use strict';
    
    /**
     * Initialisierungsfunktion für die Upload-Seite
     */
    function initUploadPage() {
        console.log('Upload-Seite initialisiert');
        
        const uploadForm = document.getElementById('upload-form');
        if (!uploadForm) return; // Nicht auf der Upload-Seite
        
        const fileInput = document.getElementById('file-input');
        const dropArea = document.getElementById('file-drop-area');
        const selectedFilesContainer = document.getElementById('selected-files');
        const uploadButton = document.getElementById('upload-button');
        
        setupFileDropArea(dropArea, fileInput, selectedFilesContainer, uploadButton);
        setupUploadForm(uploadForm);
        setupResetButton();
    }
    
    /**
     * Richtet den Drag-and-Drop-Bereich für Dateien ein
     * @param {HTMLElement} dropArea - Der Drop-Bereich
     * @param {HTMLElement} fileInput - Das Datei-Input-Element
     * @param {HTMLElement} selectedFilesContainer - Container für ausgewählte Dateien
     * @param {HTMLElement} uploadButton - Upload-Button
     */
    function setupFileDropArea(dropArea, fileInput, selectedFilesContainer, uploadButton) {
        if (!dropArea) return;
        
        // Event-Handler für Drag-and-Drop-Events
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        // Highlight-Effekt beim Draggen über den Bereich
        ['dragenter', 'dragover'].forEach(eventName => {
            dropArea.addEventListener(eventName, highlight, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, unhighlight, false);
        });
        
        function highlight() {
            dropArea.classList.add('highlight');
        }
        
        function unhighlight() {
            dropArea.classList.remove('highlight');
        }
        
        // Dateien per Drag & Drop
        dropArea.addEventListener('drop', handleDrop, false);
        
        /**
         * Verarbeitet gedropte Dateien
         * @param {DragEvent} e - Das Drop-Event
         */
        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            
            if (fileInput) {
                // DataTransfer für die Aktualisierung des FileList-Objekts verwenden
                const dtList = new DataTransfer();
                
                for (let i = 0; i < files.length; i++) {
                    dtList.items.add(files[i]);
                }
                
                fileInput.files = dtList.files;
                updateFileList();
            }
        }
        
        // Klick auf Drop-Area öffnet Datei-Dialog
        dropArea.addEventListener('click', function() {
            fileInput.click();
        });
        
        // Event-Handler für Dateiauswahl
        if (fileInput) {
            fileInput.addEventListener('change', updateFileList);
        }
        
        /**
         * Aktualisiert die Anzeige der ausgewählten Dateien
         */
        function updateFileList() {
            if (!selectedFilesContainer || !fileInput) return;
            
            selectedFilesContainer.innerHTML = '';
            
            if (fileInput.files.length > 0) {
                const fileList = document.createElement('div');
                fileList.className = 'file-list';
                
                Array.from(fileInput.files).forEach(file => {
                    const fileItem = document.createElement('div');
                    fileItem.className = 'file-item';
                    
                    // Icon je nach Dateityp
                    const fileIcon = document.createElement('div');
                    fileIcon.className = 'file-item-icon';
                    
                    let iconClass = 'fas fa-file';
                    const fileExt = file.name.toLowerCase().split('.').pop();
                    
                    // Icon basierend auf Dateityp
                    if (fileExt === 'pdf') iconClass = 'fas fa-file-pdf';
                    else if (fileExt === 'epub') iconClass = 'fas fa-book';
                    else if (fileExt === 'docx' || fileExt === 'doc') iconClass = 'fas fa-file-word';
                    else if (fileExt === 'pptx' || fileExt === 'ppt') iconClass = 'fas fa-file-powerpoint';
                    else if (fileExt === 'txt') iconClass = 'fas fa-file-alt';
                    
                    fileIcon.innerHTML = `<i class="${iconClass}"></i>`;
                    
                    // Dateiname und -größe
                    const fileInfo = document.createElement('div');
                    fileInfo.className = 'file-item-info';
                    fileInfo.innerHTML = `
                        <div class="file-name">${file.name}</div>
                        <div class="file-size">${window.scilit.formatFileSize(file.size)}</div>
                    `;
                    
                    fileItem.appendChild(fileIcon);
                    fileItem.appendChild(fileInfo);
                    fileList.appendChild(fileItem);
                });
                
                selectedFilesContainer.appendChild(fileList);
                
                if (uploadButton) {
                    uploadButton.disabled = false;
                }
            } else {
                if (uploadButton) {
                    uploadButton.disabled = true;
                }
            }
        }
    }
    
    /**
     * Richtet das Upload-Formular ein
     * @param {HTMLFormElement} form - Das Upload-Formular
     */
    function setupUploadForm(form) {
        if (!form) return;
        
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const submitButton = form.querySelector('button[type="submit"]');
            const fileInput = form.querySelector('input[type="file"]');
            
            if (!fileInput || !fileInput.files.length) {
                window.scilit.showNotification('Bitte wählen Sie mindestens eine Datei aus.', 'warning');
                return;
            }
            
            // Button-Status ändern
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Wird hochgeladen...';
            }
            
            try {
                // FormData erstellen
                const formData = new FormData(form);
                
                // AJAX-Anfrage senden
                const response = await window.scilit.fetchWithErrorHandling('/upload-with-review', {
                    method: 'POST',
                    body: formData
                });
                
                // Bei erfolgreicher Verarbeitung zur Überprüfungsseite weiterleiten
                if (response.redirected) {
                    window.location.href = response.url;
                } else {
                    // JSON-Antwort verarbeiten
                    const data = await response.json();
                    
                    if (data.redirect) {
                        window.location.href = data.redirect;
                    } else {
                        // Status zurücksetzen
                        if (submitButton) {
                            submitButton.disabled = false;
                            submitButton.innerHTML = '<i class="fas fa-upload"></i> Dokumente hochladen';
                        }
                        
                        // Erfolgsbenachrichtigung
                        window.scilit.showNotification('Dateien erfolgreich hochgeladen.', 'success');
                    }
                }
            } catch (error) {
                // Status zurücksetzen
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.innerHTML = '<i class="fas fa-upload"></i> Dokumente hochladen';
                }
                
                // Fehlerbenachrichtigung
                window.scilit.showNotification(`Fehler beim Hochladen: ${error.message}`, 'error');
                console.error('Upload-Fehler:', error);
            }
        });
    }
    
    /**
     * Richtet den Zurücksetzen-Button ein
     */
    function setupResetButton() {
        const resetButton = document.getElementById('reset-button');
        
        if (resetButton) {
            resetButton.addEventListener('click', function() {
                const selectedFilesContainer = document.getElementById('selected-files');
                const uploadButton = document.getElementById('upload-button');
                
                if (selectedFilesContainer) {
                    selectedFilesContainer.innerHTML = '';
                }
                
                if (uploadButton) {
                    uploadButton.disabled = true;
                }
            });
        }
    }
    
    // Event-Listener für das Upload-Seiten-Event
    document.addEventListener('scilit:uploadPage', initUploadPage);
    
    // Auch beim Laden der Seite initialisieren, falls die Seite direkt aufgerufen wurde
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            if (window.location.pathname.includes('/upload')) {
                initUploadPage();
            }
        });
    } else {
        if (window.location.pathname.includes('/upload')) {
            initUploadPage();
        }
    }
    
})();