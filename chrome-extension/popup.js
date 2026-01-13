// Popup script for the Chrome extension
document.addEventListener('DOMContentLoaded', function() {
  const extractBtn = document.getElementById('extractBtn');
  const copyBtn = document.getElementById('copyBtn');
  const stateOutput = document.getElementById('stateOutput');
  const statusDiv = document.getElementById('status');

  let latestSnapshot = null;

  function setLoading(isLoading) {
    extractBtn.disabled = isLoading;
    extractBtn.textContent = isLoading ? '采集中，请稍候...' : '1.点击获取环境+登录状态';
  }

  function updateStatus(message, isSuccess = false) {
    statusDiv.textContent = message;
    statusDiv.className = 'status ' + (isSuccess ? 'success' : 'error');
    setTimeout(() => {
      statusDiv.textContent = '';
      statusDiv.className = 'status';
    }, 4000);
  }

  function renderSnapshot(snapshot) {
    latestSnapshot = snapshot;
    stateOutput.value = JSON.stringify(snapshot, null, 2);
  }

  async function captureSnapshot() {
    setLoading(true);
    updateStatus('正在采集浏览器环境与登录状态...');
    stateOutput.value = '';

    chrome.runtime.sendMessage({ type: 'captureSnapshot' }, (response) => {
      setLoading(false);

      if (chrome.runtime.lastError) {
        updateStatus('通信失败: ' + chrome.runtime.lastError.message);
        return;
      }
      if (!response || !response.ok) {
        updateStatus('采集失败: ' + (response?.error || '未知错误'));
        return;
      }

      renderSnapshot(response.data);
      updateStatus('采集完成，已生成JSON', true);
    });
  }

  function copySnapshot() {
    if (!stateOutput.value) {
      updateStatus('没有可复制的数据');
      return;
    }
    navigator.clipboard.writeText(stateOutput.value)
      .then(() => updateStatus('已复制到剪贴板', true))
      .catch(err => updateStatus('复制失败: ' + err));
  }

  extractBtn.addEventListener('click', captureSnapshot);
  copyBtn.addEventListener('click', copySnapshot);
});
