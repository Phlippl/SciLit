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
    setupDocumentDetailPage();
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
        yearElement.innerHTML = yearElement.innerHTML.replace('{{ year }}', year);
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

// Dokument-Detail-Seite
function setupDocumentDetailPage() {
    // Prüfe, ob wir auf der Dokumentendetailseite sind
    const documentData = document.getElementById('document-data');
    if (!documentData) return;
    
    // Daten aus dem data-Attributen extrahieren
    const docData = {
        id: documentData.dataset.id,
        title: documentData.dataset.title,
        authors: JSON.parse(documentData.dataset.authors || '[]'),
        year: documentData.dataset.year,
        journal: documentData.dataset.journal,
        publisher: documentData.dataset.publisher,
        doi: documentData.dataset.doi,
        isbn: documentData.dataset.isbn,
        filepath: documentData.dataset.filepath,
        addedAt: documentData.dataset.addedAt,
        chunkCount: documentData.dataset.chunkCount
    };
    
    // Tab-Funktionalität
    setupTabs();
    
    // Zitieren-Funktionalität
    setupCitationBox(docData);
    
    // Metadaten bearbeiten
    setupMetadataEditing(docData);
    
    // Chunks filtern
    setupChunksFiltering();
    
    // Dokument verwalten
    setupDocumentManagement(docData);
}

// Tab-Funktionalität
function setupTabs() {
    const tabLinks = document.querySelectorAll('.tab-link');
    const tabPanes = document.querySelectorAll('.tab-pane');
    
    tabLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Tab-Links deaktivieren
            tabLinks.forEach(l => l.classList.remove('active'));
            
            // Tab-Panes ausblenden
            tabPanes.forEach(pane => pane.classList.remove('active'));
            
            // Angeklickten Tab aktivieren
            this.classList.add('active');
            
            // Entsprechenden Tab-Inhalt anzeigen
            const targetId = this.getAttribute('href').substring(1);
            document.getElementById(targetId).classList.add('active');
        });
    });
}

// Zitieren-Funktionalität
function setupCitationBox(docData) {
    const citeButton = document.getElementById('cite-document');
    const citationBox = document.getElementById('citation-box');
    const closeButton = document.querySelector('.citation-close');
    const styleBtns = document.querySelectorAll('.citation-style-btn');
    const copyButton = document.getElementById('copy-citation');
    
    if (!citeButton || !citationBox) return;
    
    // Zitieren-Box anzeigen
    citeButton.addEventListener('click', function() {
        citationBox.style.display = 'block';
    });
    
    // Zitieren-Box schließen
    closeButton.addEventListener('click', function() {
        citationBox.style.display = 'none';
    });
    
    // Zitierstil ändern
    styleBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            styleBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            const style = this.getAttribute('data-style');
            updateCitationStyle(style, docData);
        });
    });
    
    // Zitation kopieren
    copyButton.addEventListener('click', function() {
        const citationText = document.getElementById('citation-text').innerText;
        navigator.clipboard.writeText(citationText)
            .then(() => {
                this.innerHTML = '<i class="fas fa-check"></i> Kopiert!';
                setTimeout(() => {
                    this.innerHTML = '<i class="fas fa-copy"></i> Kopieren';
                }, 2000);
            })
            .catch(err => {
                console.error('Fehler beim Kopieren: ', err);
            });
    });
}

// Funktion zum Aktualisieren des Zitierstils
function updateCitationStyle(style, docData) {
    const citationText = document.getElementById('citation-text');
    if (!citationText) return;
    
    const { authors, title, year, journal, publisher, doi } = docData;
    let citation = '';
    
    switch (style) {
        case 'apa':
            // APA-Stil
            if (authors && authors.length > 0) {
                for (let i = 0; i < authors.length; i++) {
                    const nameParts = authors[i].split(' ');
                    const lastName = nameParts[nameParts.length - 1];
                    const initials = nameParts.slice(0, -1).map(n => n[0] + '.').join(' ');
                    
                    citation += lastName + ', ' + initials;
                    
                    if (i < authors.length - 2) {
                        citation += ', ';
                    } else if (i === authors.length - 2) {
                        citation += ', & ';
                    }
                }
                
                citation += ' ';
            }
            
            citation += `(${year}). `;
            citation += `${title}. `;
            
            if (journal) {
                citation += `<em>${journal}</em>`;
            } else if (publisher) {
                citation += publisher;
            }
            
            if (doi) {
                citation += `. https://doi.org/${doi}`;
            }
            break;
            
        case 'mla':
            // MLA-Stil
            if (authors && authors.length > 0) {
                const firstAuthor = authors[0].split(' ');
                const firstAuthorLastName = firstAuthor[firstAuthor.length - 1];
                const firstAuthorFirstName = firstAuthor.slice(0, -1).join(' ');
                
                citation += `${firstAuthorLastName}, ${firstAuthorFirstName}`;
                
                if (authors.length > 1) {
                    citation += ', et al';
                }
                
                citation += '. ';
            }
            
            citation += `<em>${title}</em>. `;
            
            if (publisher) {
                citation += `${publisher}, `;
            }
            
            citation += year + '.';
            
            if (doi) {
                citation += ` DOI: ${doi}`;
            }
            break;
            
        case 'chicago':
            // Chicago-Stil
            if (authors && authors.length > 0) {
                for (let i = 0; i < authors.length; i++) {
                    const nameParts = authors[i].split(' ');
                    const lastName = nameParts[nameParts.length - 1];
                    const firstName = nameParts.slice(0, -1).join(' ');
                    
                    if (i === 0) {
                        citation += lastName + ', ' + firstName;
                    } else {
                        citation += firstName + ' ' + lastName;
                    }
                    
                    if (i < authors.length - 2) {
                        citation += ', ';
                    } else if (i === authors.length - 2) {
                        citation += ', and ';
                    }
                }
                
                citation += '. ';
            }
            
            citation += `<em>${title}</em>. `;
            
            if (publisher) {
                citation += `${publisher}, `;
            }
            
            citation += year + '.';
            
            if (doi) {
                citation += ` https://doi.org/${doi}.`;
            }
            break;
            
        case 'harvard':
            // Harvard-Stil
            if (authors && authors.length > 0) {
                for (let i = 0; i < authors.length; i++) {
                    const nameParts = authors[i].split(' ');
                    const lastName = nameParts[nameParts.length - 1];
                    const initials = nameParts.slice(0, -1).map(n => n[0] + '.').join('');
                    
                    citation += lastName + ', ' + initials;
                    
                    if (i < authors.length - 2) {
                        citation += ', ';
                    } else if (i === authors.length - 2) {
                        citation += ' and ';
                    }
                }
                
                citation += ' ';
            }
            
            citation += `(${year}) `;
            citation += `<em>${title}</em>, `;
            
            if (publisher) {
                citation += `${publisher}.`;
            } else if (journal) {
                citation += `${journal}.`;
            }
            
            if (doi) {
                citation += ` Available at: https://doi.org/${doi} (Accessed: ${new Date().toLocaleDateString()}).`;
            }
            break;
    }
    
    citationText.innerHTML = citation;
}

// Metadaten bearbeiten
function setupMetadataEditing(docData) {
    const editMetadataBtn = document.getElementById('edit-metadata');
    const metadataForm = document.getElementById('metadata-form');
    const cancelEditBtn = document.getElementById('cancel-edit');
    const editForm = document.getElementById('edit-metadata-form');
    
    if (!editMetadataBtn || !metadataForm) return;
    
    // Formular anzeigen
    editMetadataBtn.addEventListener('click', function() {
        metadataForm.style.display = 'block';
    });
    
    // Formular ausblenden
    cancelEditBtn.addEventListener('click', function() {
        metadataForm.style.display = 'none';
    });
    
    // Formular absenden
    editForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Metadaten sammeln
        const metadata = {
            title: document.getElementById('edit-title').value,
            author: document.getElementById('edit-authors').value.split(',').map(a => a.trim()),
            year: document.getElementById('edit-year').value,
            journal: document.getElementById('edit-journal').value,
            publisher: document.getElementById('edit-publisher').value,
            doi: document.getElementById('edit-doi').value,
            isbn: document.getElementById('edit-isbn').value
        };
        
        // API-Aufruf zum Aktualisieren der Metadaten
        fetch(`/documents/${docData.id}/metadata`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(metadata)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Formular ausblenden und Seite neu laden
                metadataForm.style.display = 'none';
                window.location.reload();
            } else {
                alert('Fehler beim Aktualisieren der Metadaten');
            }
        })
        .catch(error => {
            console.error('Fehler:', error);
            alert('Fehler beim Aktualisieren der Metadaten');
        });
    });
}

// Chunks filtern
function setupChunksFiltering() {
    const filterInput = document.getElementById('filter-chunks');
    const chunkItems = document.querySelectorAll('.chunk-item');
    const filterCount = document.querySelector('.filter-count');
    
    if (!filterInput) return;
    
    filterInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        let visibleCount = 0;
        
        chunkItems.forEach(item => {
            const chunkText = item.querySelector('.chunk-text').textContent.toLowerCase();
            const matchesSearch = chunkText.includes(searchTerm);
            
            item.style.display = matchesSearch ? 'block' : 'none';
            
            if (matchesSearch) {
                visibleCount++;
            }
        });
        
        filterCount.textContent = `${visibleCount} von ${chunkItems.length} Chunks`;
    });
}

// Dokument verwalten (löschen, neu verarbeiten, exportieren)
function setupDocumentManagement(docData) {
    // Dokument löschen
    setupDocumentDeletion(docData);
    
    // Dokument neu verarbeiten
    setupDocumentReprocessing(docData);
    
    // Metadaten exportieren
    setupMetadataExport(docData);
}

// Dokument löschen
function setupDocumentDeletion(docData) {
    const deleteBtn = document.getElementById('delete-document');
    const deleteConfirmation = document.getElementById('delete-confirmation');
    const confirmDeleteBtn = document.getElementById('confirm-delete');
    const cancelDeleteBtn = document.getElementById('cancel-delete');
    
    if (!deleteBtn || !deleteConfirmation) return;
    
    // Bestätigung anzeigen
    deleteBtn.addEventListener('click', function() {
        deleteConfirmation.style.display = 'block';
    });
    
    // Abbrechen
    cancelDeleteBtn.addEventListener('click', function() {
        deleteConfirmation.style.display = 'none';
    });
    
    // Löschen bestätigen
    confirmDeleteBtn.addEventListener('click', function() {
        // API-Aufruf zum Löschen des Dokuments
        fetch(`/documents/${docData.id}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                window.location.href = '/documents';
            } else {
                alert('Fehler beim Löschen des Dokuments');
            }
        })
        .catch(error => {
            console.error('Fehler:', error);
            alert('Fehler beim Löschen des Dokuments');
        });
    });
}

// Dokument neu verarbeiten
function setupDocumentReprocessing(docData) {
    const reprocessBtn = document.getElementById('reprocess-document');
    
    if (!reprocessBtn) return;
    
    reprocessBtn.addEventListener('click', function() {
        if (confirm('Möchtest du das Dokument neu verarbeiten? Dies kann einige Zeit dauern.')) {
            this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Wird verarbeitet...';
            this.disabled = true;
            
            // API-Aufruf zum Neuverarbeiten des Dokuments
            fetch(`/documents/${docData.id}/reprocess`, {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    window.location.reload();
                } else {
                    alert('Fehler beim Neuverarbeiten des Dokuments');
                    this.innerHTML = '<i class="fas fa-sync"></i> Dokument neu verarbeiten';
                    this.disabled = false;
                }
            })
            .catch(error => {
                console.error('Fehler:', error);
                alert('Fehler beim Neuverarbeiten des Dokuments');
                this.innerHTML = '<i class="fas fa-sync"></i> Dokument neu verarbeiten';
                this.disabled = false;
            });
        }
    });
}

// Metadaten exportieren
function setupMetadataExport(docData) {
    const exportBtn = document.getElementById('export-document');
    
    if (!exportBtn) return;
    
    exportBtn.addEventListener('click', function() {
        // Metadaten für den Export vorbereiten
        const exportMetadata = {
            title: docData.title,
            authors: docData.authors,
            year: docData.year,
            source: docData.journal || docData.publisher || '',
            doi: docData.doi,
            isbn: docData.isbn
        };
        
        // Als JSON exportieren
        const blob = new Blob([JSON.stringify(exportMetadata, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        // Download initiieren
        const a = document.createElement('a');
        a.href = url;
        a.download = `${docData.title.replace(/\s+/g, '_')}_metadata.json`;
        a.click();
        
        URL.revokeObjectURL(url);
    });
}