let baseUrls = [];
let extraUrls = [];
let fileUrls = [];
let selectedTextFile = null;


function isValidURL(url) {
    let urlPattern = /^(https?:\/\/)?([a-zA-Z0-9.-]+)\.[a-zA-Z]{2,6}(\/\S*)?$/;
    return urlPattern.test(url);
}

function loadURLFile() {
    const input = document.getElementById("urls-file");
    const file = input.files && input.files[0];

    if (!file) {
        showError("Please choose a .txt file first.");
        return;
    }

    if (!file.name.toLowerCase().endsWith(".txt")) {
        showError("Only .txt files are allowed.");
        return;
    }

    selectedTextFile = file;

    const reader = new FileReader();
    reader.onload = function (event) {
        const content = event.target.result || "";
        const urls = content.split(/\r?\n/)
            .map(line => line.trim())
            .filter(line => line && !line.startsWith("#"))
            .filter((line, index, arr) => arr.indexOf(line) === index);

        fileUrls = urls;
        updateFileUrlList();
    };
    reader.readAsText(file);
}

function addBaseURL() {
    let baseUrlInput = document.getElementById("base-url");
    let url = baseUrlInput.value.trim();

    if (!url) {
        showError("Please enter a valid Base URL.");
        return;
    }
    if (!isValidURL(url)) {
        showError("Base URL must be a valid URL format (http/https).");
        return;
    }

    if (!url.toLowerCase().includes("sitemap")) {
        showError("Base URL must contain the word 'sitemap'.");
        return;
    }

    if (baseUrls.includes(url)) {
        showError("This Base URL is already added.");
        return;
    }

    baseUrls.push(url);
    updateBaseUrlList();
    baseUrlInput.value = "";
}

function addExtraURL() {
    let extraUrlInput = document.getElementById("extra-url");
    let url = extraUrlInput.value.trim();

    if (url.toLowerCase().includes("sitemap")) {
        showError("URL must contain non sitemap urls.");
        return;
    }

    if (!url) {
        showError("Please enter a valid Additional URL.");
        return;
    }
    if (!isValidURL(url)) {
        showError("Additional URL must be a valid URL format (http/https).");
        return;
    }

    if (extraUrls.includes(url)) {
        showError("This Additional URL is already added.");
        return;
    }

    extraUrls.push(url);
    updateExtraUrlList();
    extraUrlInput.value = "";
}

function updateBaseUrlList() {
    let list = document.getElementById("base-url-list");
    list.innerHTML = "";
    baseUrls.forEach((url, index) => {
        list.innerHTML += `<li>${url} <button onclick="removeBaseUrl(${index})">X</button></li>`;
    });
}

function updateExtraUrlList() {
    let list = document.getElementById("extra-url-list");
    list.innerHTML = "";
    extraUrls.forEach((url, index) => {
        list.innerHTML += `<li>${url} <button onclick="removeExtraUrl(${index})">X</button></li>`;
    });
}

function updateFileUrlList() {
    let list = document.getElementById("file-url-list");
    list.innerHTML = "";
    fileUrls.forEach((url, index) => {
        list.innerHTML += `<li>${url} <button onclick="removeFileUrl(${index})">X</button></li>`;
    });
}

function removeBaseUrl(index) {
    baseUrls.splice(index, 1);
    updateBaseUrlList();
}

function removeExtraUrl(index) {
    extraUrls.splice(index, 1);
    updateExtraUrlList();
}

function removeFileUrl(index) {
    fileUrls.splice(index, 1);
    updateFileUrlList();
}

function showError(message) {
    let errorMessage = document.getElementById("error-message");
    errorMessage.innerText = message;
    setTimeout(() => {
        errorMessage.innerText = "";
    }, 3000);
}

function displayOutput(data) {
    let outputDiv = document.getElementById("output");
    
    let html = `<div style="padding: 20px; background-color: #e8f5e9; border-radius: 8px; border-left: 4px solid #4caf50;">`;
    html += `<h2 style="color: #2e7d32;">✓ ${data.message}</h2>`;
    
    html += `<p><strong>Total URLs processed:</strong> ${data.total_urls}</p>`;
    if (data.unscraped_count > 0) {
        html += `<p style="color: #d32f2f;"><strong>Unscraped URLs (${data.unscraped_count}):</strong></p>`;
        html += `<ul>${data.unscraped_urls.map(url => `<li>${url}</li>`).join('')}</ul>`;
    }
    
    html += `<hr style="border: none; border-top: 1px solid #ccc; margin: 20px 0;">`;
    html += `<p style="font-size: 16px; color: #1976d2;"><strong>Next Step:</strong> ${data.next_action}</p>`;
    html += `<button class="submit-btn" onclick="window.location.href='${data.chat_url}'" style="background-color: #4caf50; font-size: 16px; padding: 12px 24px;">Open Organization-Specific LLM Chat</button>`;
    html += `</div>`;
    
    outputDiv.innerHTML = html;
    outputDiv.style.display = "block";
}

function submitData() {
    const allUrls = [...baseUrls, ...extraUrls, ...fileUrls];

    if (allUrls.length === 0) {
        showError("At least one URL (Base, Extra, or .txt file) must be provided.");
        return;
    }

    const formData = new FormData();
    formData.append("base_urls", JSON.stringify(baseUrls));
    formData.append("extra_urls", JSON.stringify([...extraUrls, ...fileUrls]));

    if (selectedTextFile) {
        formData.append("urls_file", selectedTextFile);
    }

    fetch('/submit-urls', {
        method: "POST",
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        displayOutput(data);
        baseUrls = [];
        extraUrls = [];
        fileUrls = [];
        selectedTextFile = null;
        document.getElementById("urls-file").value = "";
        updateBaseUrlList();
        updateExtraUrlList();
        updateFileUrlList();
    })
    .catch(error => {
        showError("Error submitting URLs");
        console.error(error);
    });
}
