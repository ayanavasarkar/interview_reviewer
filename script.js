document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const recordBtn = document.getElementById('recordBtn');
    const audioFileInput = document.getElementById('audioFile');
    const fileNameDisplay = document.getElementById('fileName');
    const statusDiv = document.getElementById('status');
    const statusText = document.getElementById('statusText');
    const feedbackReportDiv = document.getElementById('feedbackReport');
    const transcriptText = document.getElementById('transcriptText');
    const strengthsText = document.getElementById('strengthsText');
    const weaknessesText = document.getElementById('weaknessesText');
    const recommendationsText = document.getElementById('recommendationsText');
    const resetBtn = document.getElementById('resetBtn');
    const controlsDiv = document.querySelector('.controls');

    // --- State Variables ---
    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;
    // const API_ENDPOINT = "http://127.0.0.1:8000/analyze-interview/";
    const API_ENDPOINT = "/analyze";
    // const API_ENDPOINT = window.location.origin + "/analyze";


    // --- Media Recorder Functions ---
    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            
            mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                const audioFile = new File([audioBlob], "recording.wav", { type: "audio/wav" });
                sendAudioToServer(audioFile);
                audioChunks = [];
            };

            mediaRecorder.start();
            isRecording = true;
            updateRecordingUI();
        } catch (error) {
            console.error("Error accessing microphone:", error);
            alert("Could not access microphone. Please ensure permissions are granted.");
        }
    };

    const stopRecording = () => {
        if(mediaRecorder) mediaRecorder.stop();
        isRecording = false;
        updateRecordingUI();
    };

    const updateRecordingUI = () => {
        if (isRecording) {
            recordBtn.textContent = 'Stop Recording';
            recordBtn.classList.add('recording');
        } else {
            recordBtn.textContent = 'Start Recording';
            recordBtn.classList.remove('recording');
        }
    };

    // --- API Communication ---
    const sendAudioToServer = async (file) => {
        const formData = new FormData();
        formData.append("file", file);

        showStatus("Uploading and analyzing... This may take a moment.");

        try {
            const response = await fetch(API_ENDPOINT, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error! Status: ${response.status}`);
            }

            const result = await response.json();
            displayFeedback(result);

        } catch (error) {
            console.error("Error sending audio to server:", error);
            showError(`Analysis failed: ${error.message}`);
        }
    };

    // --- UI Update Functions ---
    const showStatus = (message) => {
        controlsDiv.style.display = 'none';
        statusDiv.classList.remove('status-hidden');
        feedbackReportDiv.classList.add('report-hidden');
        statusText.textContent = message;
        statusDiv.querySelector('.loader').style.display = 'block';
    };
    
    const showError = (message) => {
        statusText.textContent = message;
        statusDiv.querySelector('.loader').style.display = 'none';
    };

    const displayFeedback = (data) => {
        statusDiv.classList.add('status-hidden');
        feedbackReportDiv.classList.remove('report-hidden');

        // Helper function to convert newline characters to HTML breaks
        const formatText = (text = "") => text.replace(/\n/g, '<br>');

        // Display transcript using .innerHTML
        transcriptText.innerHTML = formatText(data.transcript || "Transcript not available.");

        // Display other feedback using .innerHTML
        strengthsText.innerHTML = formatText(data.strengths || "N/A");
        weaknessesText.innerHTML = formatText(data.weaknesses || "N/A");
        recommendationsText.innerHTML = formatText(data.recommendations || "N/A");
    };

    const resetUI = () => {
        controlsDiv.style.display = 'flex';
        statusDiv.classList.add('status-hidden');
        feedbackReportDiv.classList.add('report-hidden');
        audioFileInput.value = '';
        fileNameDisplay.textContent = 'No file chosen';
        transcriptText.innerHTML = '';
        strengthsText.innerHTML = '';
        weaknessesText.innerHTML = '';
        recommendationsText.innerHTML = '';
    };

    // --- Event Listeners ---
    recordBtn.addEventListener('click', () => {
        if (isRecording) stopRecording();
        else startRecording();
    });

    audioFileInput.addEventListener('change', () => {
        const file = audioFileInput.files[0];
        if (file) {
            fileNameDisplay.textContent = file.name;
            sendAudioToServer(file);
        }
    });
    
    resetBtn.addEventListener('click', resetUI);
});