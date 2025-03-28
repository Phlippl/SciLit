document.addEventListener('DOMContentLoaded', function() {
    console.log('SciLit App initialized');
    
    // Funktionen für alle Seiten
    setupMobileNavigation();
    setupCollapsibleSections();
    setupFooterDate();
    
    // Seitenspezifische Funktionen
    setupUploadPage();
    setupSearchPage();
    setupDocumentsPage();
});

// Mobile Navigation
function setupMobileNavigation() {
    // In zukünftigen Versionen zu implementieren
}

// Erweiterbare/Ausklappbare Abschnitte
function setupCollapsibleSections() {
    const toggleButtons = document.querySelectorAll('[data-toggle]');
    
    toggleButtons.forEach(button => {
        button.addEventListener('click', function() {
            const targetId = this.getAttribute('data-toggle');
            const targetElement = document.getElementById(targetId);
            
            if (targetElement) {
                const isVisible = targetElement.style.display !== 'none';
                
                if (isVisible) {
                    targetElement.style.display = 'none';
                    this.innerHTML = this.innerHTML.replace('fa-chevron-up', 'fa-chevron-down');
                } else {
                    targetElement.style.display = 'block';
                    this.innerHTML = this.innerHTML.replace('fa-chevron-down', 'fa-chevron-up');
                }
            }
        });
    });
}

// Upload-Seite
function setupUploadPage() {
    const uploadForm = document.getElementById('upload-form');
    if (!uploadForm) return; // Nicht auf der Upload-Seite
    
    const fileInput = document.getElementById('file-input');
    const dropArea = document.getElementById('file-drop-area');
    const selectedFilesContainer = document.getElementById('selected-files');
    const uploadButton = document.getElementById('upload-button');
    
    if (dropArea) {
        // Drag & Drop-Funktionalität
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
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
        
        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            
            if (fileInput) {
                // Kann nicht direkt zugewiesen werden, daher DataTransfer verwenden
                const dtList = new DataTransfer();
                
                for (let i = 0; i < files.length; i++) {
                    dtList.items.add(files[i]);
                }
                
                fileInput.files = dtList.files;
                updateFileList();
            }
        }
        
        // Klikc auf Drop-Area
        dropArea.addEventListener('click', function() {
            fileInput.click();
        });
    }
    
    if (fileInput) {
        fileInput.addEventListener('change', updateFileList);
    }
    
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
                if (file.name.endsWith('.pdf')) iconClass = 'fas fa-file-pdf';
                else if (file.name.endsWith('.epub')) iconClass = 'fas fa-book';
                else if (file.name.endsWith('.docx')) iconClass = 'fas fa-file-word';
                else if (file.name.endsWith('.pptx')) iconClass = 'fas fa-file-powerpoint';
                else if (file.name.endsWith('.txt')) iconClass = 'fas fa-file-alt';
                
                fileIcon.innerHTML = `<i class="${iconClass}"></i>`;
                
                // Dateiname und -größe
                const fileInfo = document.createElement('div');
                fileInfo.className = 'file-item-info';
                fileInfo.innerHTML = `
                    <div class="file-name">${file.name}</div>
                    <div class="file-size">${formatFileSize(file.size)}</div>
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
    
    // Dateigröße formatieren
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    // Ergebnisse ausblenden
    const clearResultsButton = document.getElementById('clear-results');
    if (clearResultsButton) {
        clearResultsButton.addEventListener('click', function() {
            const resultsContainer = document.querySelector('.upload-results');
            if (resultsContainer) {
                resultsContainer.style.display = 'none';
            }
        });
    }
}

// Fußzeile mit aktuellem Jahr aktualisieren
function setupFooterDate() {
    const yearElement = document.querySelector('footer .container p');
    if (yearElement) {
        const year = new Date().getFullYear();
        yearElement.innerHTML = yearElement.innerHTML.replace('{% now \'Y\' %}', year);
    }
}

// Suchseite
function setupSearchPage() {
    const searchForm = document.querySelector('.search-form');
    if (!searchForm) return; // Nicht auf der Suchseite
    
    // Erweiterte Suchoptionen ein-/ausblenden
    const toggleAdvancedButton = document.getElementById('toggle-advanced');
    const advancedOptions = document.getElementById('advanced-options');
    
    if (toggleAdvancedButton && advancedOptions) {
        toggleAdvancedButton.addEventListener('click', function() {
            const isVisible = advancedOptions.style.display !== 'none';
            
            if (isVisible) {
                advancedOptions.style.display = 'none';
                toggleAdvancedButton.innerHTML = '<i class="fas fa-cog"></i> Erweiterte Optionen anzeigen';
            } else {
                advancedOptions.style.display = 'block';
                toggleAdvancedButton.innerHTML = '<i class="fas fa-cog"></i> Erweiterte Optionen ausblenden';
            }
        });
    }
    
    // Suchtyp ändern
    const searchTypeSelect = document.getElementById('search-type');
    const citationStyleContainer = document.getElementById('citation-style-container');
    
    if (searchTypeSelect && citationStyleContainer) {
        searchTypeSelect.addEventListener('change', function() {
            if (this.value === 'question') {
                citationStyleContainer.style.display = 'block';
            } else {
                citationStyleContainer.style.display = 'none';
            }
        });
    }
}

// Dokumente-Seite
function setupDocumentsPage() {
    const documentsContainer = document.querySelector('.documents-list');
    if (!documentsContainer) return; // Nicht auf der Dokumente-Seite
    
    // Filter-Funktionalität
    const filterInput = document.getElementById('filter-documents');
    if (filterInput) {
        filterInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const documentItems = document.querySelectorAll('.document-item');
            
            documentItems.forEach(item => {
                const title = item.querySelector('.document-title').textContent.toLowerCase();
                const authors = item.querySelector('.document-authors').textContent.toLowerCase();
                const matchesSearch = title.includes(searchTerm) || authors.includes(searchTerm);
                
                item.style.display = matchesSearch ? 'block' : 'none';
            });
        });
    }
    
    // Sortierung
    const sortSelect = document.getElementById('sort-documents');
    if (sortSelect) {
        sortSelect.addEventListener('change', function() {
            const sortBy = this.value;
            const documentItems = Array.from(document.querySelectorAll('.document-item'));
            
            documentItems.sort((a, b) => {
                let valueA, valueB;
                
                switch (sortBy) {
                    case 'title':
                        valueA = a.querySelector('.document-title').textContent;
                        valueB = b.querySelector('.document-title').textContent;
                        return valueA.localeCompare(valueB);
                    case 'author':
                        valueA = a.querySelector('.document-authors').textContent;
                        valueB = b.querySelector('.document-authors').textContent;
                        return valueA.localeCompare(valueB);
                    case 'year':
                        valueA = parseInt(a.querySelector('.document-year').textContent);
                        valueB = parseInt(b.querySelector('.document-year').textContent);
                        return valueB - valueA; // Neueste zuerst
                    case 'added':
                        valueA = new Date(a.dataset.addedDate);
                        valueB = new Date(b.dataset.addedDate);
                        return valueB - valueA; // Neueste zuerst
                    default:
                        return 0;
                }
            });
            
            // DOM neu anordnen
            const parent = documentsContainer;
            documentItems.forEach(item => parent.appendChild(item));
        });
    }
}