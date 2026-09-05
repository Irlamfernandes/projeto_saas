document.addEventListener('DOMContentLoaded', function() {
    
    const inputs = document.querySelectorAll('input, textarea, select');
    inputs.forEach(input => {
        input.addEventListener('focus', () => {
            setTimeout(() => {
                input.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 300);
        });
    });

    const custoInput = document.getElementById('id_preco_custo') || document.getElementById('edit-preco-custo');
    const margemInput = document.getElementById('id_margem_lucro') || document.getElementById('edit-margem-lucro');
    const vendaInput = document.getElementById('id_preco_venda') || document.getElementById('edit-preco-venda');

    if (custoInput && vendaInput) {
        if (margemInput) {
            margemInput.addEventListener('input', function() {
                const custo = parseFloat(custoInput.value) || 0;
                const margem = parseFloat(margemInput.value) || 0;
                if (custo > 0) {
                    vendaInput.value = (custo + (custo * (margem / 100))).toFixed(2);
                }
            });
        }

        vendaInput.addEventListener('input', function() {
            const custo = parseFloat(custoInput.value) || 0;
            const venda = parseFloat(vendaInput.value) || 0;
            if (custo > 0 && venda >= custo && margemInput) {
                margemInput.value = (((venda - custo) / custo) * 100).toFixed(2);
            }
        });
    }

    const selectCategoria = document.getElementById('select-categoria');
    if (selectCategoria && selectCategoria.options.length <= 2) {
        selectCategoria.value = '__novo__';
        tratarMudancaCategoria(selectCategoria);
    }
});


function tratarMudancaCategoria(select) {
    const inputNova = document.getElementById('input-nova-categoria');
    if (!inputNova) return;
    if (select.value === '__novo__') {
        select.removeAttribute('name');
        inputNova.classList.remove('hidden');
        inputNova.setAttribute('required', 'true');
        inputNova.focus();
    } else {
        select.setAttribute('name', 'categoria');
        inputNova.removeAttribute('required');
        inputNova.classList.add('hidden');
        inputNova.value = '';
    }
}

function marcarParaRemover(id, wrapper) {
    const inputRemover = document.getElementById('remover_imagens');
    let idsAtuais = inputRemover.value ? inputRemover.value.split(',') : [];
    
    if (!idsAtuais.includes(id)) {
        idsAtuais.push(id);
        inputRemover.value = idsAtuais.join(',');
    }

    wrapper.style.transition = "all 0.3s ease";
    wrapper.style.opacity = "0";
    wrapper.style.transform = "scale(0.8)";
    
    setTimeout(() => {
        wrapper.remove();
    }, 300);
}

function abrirModalEdicaoCliente(id, nome, telefone, email, endereco) {
    const modal = document.getElementById('modal-edicao-cliente');
    const form = document.getElementById('form-edicao-cliente');
    if (!modal || !form) return;
    
    form.action = `/clientes/editar/${id}/`;
    document.getElementById('edit-cli-nome').value = nome;
    document.getElementById('edit-cli-telefone').value = telefone;
    document.getElementById('edit-cli-email').value = email;
    document.getElementById('edit-cli-endereco').value = endereco;

    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

function fecharModalEdicaoCliente() {
    const modal = document.getElementById('modal-edicao-cliente');
    if (!modal) return;
    modal.classList.remove('flex');
    modal.classList.add('hidden');
}

/* istanbul ignore next */
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { 
        tratarMudancaCategoria, 
        marcarParaRemover, 
        abrirModalEdicaoCliente, 
        fecharModalEdicaoCliente 
    };
}