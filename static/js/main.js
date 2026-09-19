let imagensGaleria = [];
let indiceImagemAtual = 0;

document.addEventListener('DOMContentLoaded', function() {
    inicializarFocoInputs();
    inicializarCalculadoraPrecos();
    inicializarCategoriaPadrao();
    inicializarFecharModalAoClicarFora();
    inicializarModalGaleria();
});

function inicializarFocoInputs() {
    const inputs = document.querySelectorAll('input, textarea, select');
    inputs.forEach(input => {
        input.addEventListener('focus', () => {
            setTimeout(() => {
                input.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 300);
        });
    });
}

function inicializarCalculadoraPrecos() {
    const custoInput = document.getElementById('id_preco_custo') || document.getElementById('edit-preco-custo');
    const margemInput = document.getElementById('id_margem_lucro') || document.getElementById('edit-margem-lucro');
    const vendaInput = document.getElementById('id_preco_venda') || document.getElementById('edit-preco-venda');

    if (!custoInput || !vendaInput) return;

    if (margemInput) {
        margemInput.addEventListener('input', () => atualizarPrecoVenda(custoInput, margemInput, vendaInput));
    }

    vendaInput.addEventListener('input', () => atualizarMargemLucro(custoInput, margemInput, vendaInput));
}

function atualizarPrecoVenda(custoInput, margemInput, vendaInput) {
    const custo = Number.parseFloat(custoInput.value) || 0;
    const margem = Number.parseFloat(margemInput.value) || 0;
    
    if (custo <= 0) return;
    vendaInput.value = (custo + (custo * (margem / 100))).toFixed(2);
}

function atualizarMargemLucro(custoInput, margemInput, vendaInput) {
    const custo = Number.parseFloat(custoInput.value) || 0;
    const venda = Number.parseFloat(vendaInput.value) || 0;
    
    if (!margemInput || custo <= 0 || venda < custo) return;
    margemInput.value = (((venda - custo) / custo) * 100).toFixed(2);
}

function inicializarCategoriaPadrao() {
    const selectCategoria = document.getElementById('select-categoria');
    if (selectCategoria && selectCategoria.options.length <= 2) {
        selectCategoria.value = '__novo__';
        tratarMudancaCategoria(selectCategoria);
    }
}

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
    const idsAtuais = inputRemover.value ? inputRemover.value.split(',') : [];
    
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

    if (typeof modal.showModal === 'function') {
        modal.showModal();
    }
}

function fecharModalEdicaoCliente() {
    const modal = document.getElementById('modal-edicao-cliente');
    if (!modal) return;
    
    if (typeof modal.close === 'function') {
        modal.close();
    }
}

function inicializarFecharModalAoClicarFora() {
    const modal = document.getElementById('modal-edicao-cliente');
    if (!modal) return;

    modal.addEventListener('click', (event) => {
        const rect = modal.getBoundingClientRect();
        const isInDialog = (
            rect.top <= event.clientY &&
            event.clientY <= rect.top + rect.height &&
            rect.left <= event.clientX &&
            event.clientX <= rect.left + rect.width
        );
        if (!isInDialog) {
            fecharModalEdicaoCliente();
        }
    });
}

function inicializarModalGaleria() {
    const modal = document.getElementById('modal-imagem');
    if (!modal) return;

    modal.addEventListener('click', (event) => {
        if (event.target === modal) {
            fecharModalDireto();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !modal.classList.contains('hidden')) {
            fecharModalDireto();
        } else if (!modal.classList.contains('hidden')) {
            if (event.key === 'ArrowLeft') mudarImagem(-1);
            if (event.key === 'ArrowRight') mudarImagem(1);
        }
    });
}

function abrirModalGaleria(listaUrls, indiceInicial = 0) {
    if (!listaUrls || listaUrls.length === 0) return;

    imagensGaleria = listaUrls;
    indiceImagemAtual = indiceInicial;

    const modal = document.getElementById('modal-imagem');
    if (!modal) return;

    atualizarExibicaoGaleria();
    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

function mudarImagem(direcao) {
    if (imagensGaleria.length <= 1) return;

    indiceImagemAtual += direcao;
    if (indiceImagemAtual < 0) {
        indiceImagemAtual = imagensGaleria.length - 1;
    } else if (indiceImagemAtual >= imagensGaleria.length) {
        indiceImagemAtual = 0;
    }

    atualizarExibicaoGaleria();
}

function atualizarExibicaoGaleria() {
    const imgElement = document.getElementById('modal-imagem-src');
    const indicador = document.getElementById('modal-indicador');
    const btnAnt = document.getElementById('btn-anterior');
    const btnProx = document.getElementById('btn-proximo');

    if (imgElement) {
        imgElement.src = imagensGaleria[indiceImagemAtual];
    }

    if (indicador) {
        indicador.textContent = `${indiceImagemAtual + 1} de ${imagensGaleria.length}`;
    }

    const exibirControles = imagensGaleria.length > 1;
    if (btnAnt) btnAnt.style.display = exibirControles ? 'block' : 'none';
    if (btnProx) btnProx.style.display = exibirControles ? 'block' : 'none';
}

function fecharModalDireto() {
    const modal = document.getElementById('modal-imagem');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { 
        tratarMudancaCategoria, 
        marcarParaRemover, 
        abrirModalEdicaoCliente, 
        fecharModalEdicaoCliente,
        fecharModalDireto,
        abrirModalGaleria,
        mudarImagem
    };
}