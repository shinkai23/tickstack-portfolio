// モーダルについてのJS
function openModal(id) {
    document.getElementById(id).style.display = "flex";
}

function closeModal(id) {
    document.getElementById(id).style.display = "none";
}

// 月ごとに日の最大値を切り替える
window.addEventListener('DOMContentLoaded', function () {
    const monthInput = document.getElementById('month');
    const dayInput = document.getElementById('day');
    if (!monthInput || !dayInput) return;

    function updateDayMax() {
        const month = parseInt(monthInput.value, 10);
        let maxDay = 31;
        if ([4, 6, 9, 11].includes(month)) {
            maxDay = 30;
        } else if (month === 2) {
            maxDay = 28; // 閏年対応は省略
        }
        dayInput.max = maxDay;
        if (parseInt(dayInput.value, 10) > maxDay) {
            dayInput.value = maxDay;
        }
    }

    monthInput.addEventListener('input', updateDayMax);
    updateDayMax();
});