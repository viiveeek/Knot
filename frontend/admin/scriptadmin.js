// Chart.js Configuration
const ctx = document.getElementById('utilizationChart').getContext('2d');
new Chart(ctx, {
    type: 'bar',
    data: {
        labels: ['AR/VR Lab', 'DSLR Kit', 'Seminar Hall', 'Projector', 'IoT Lab'],
        datasets: [{
            label: 'Usage (Hours)',
            data: [120, 80, 150, 40, 95],
            backgroundColor: '#3b82f6',
            borderRadius: 8
        }]
    },
    options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
            y: { beginAtZero: true, grid: { display: false } },
            x: { grid: { display: false } }
        }
    }
});

// Approval Interaction (Fake response for demo)
document.querySelectorAll('.btn-approve').forEach(btn => {
    btn.addEventListener('click', function() {
        const row = this.closest('tr');
        row.style.opacity = '0.5';
        row.innerHTML = `<td colspan="4" class="py-4 text-center text-green-600 font-bold">Approved ✅</td>`;
        setTimeout(() => row.remove(), 1000);
    });
});