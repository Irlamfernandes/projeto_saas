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
    // Só em telas de toque: evita que o teclado virtual cubra o campo. No computador a página não pula.
    if (!globalThis.matchMedia?.('(pointer: coarse)').matches) return;
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

    // Na edição, o lucro guardado pode estar vazio/zerado: mostra o lucro real do custo e preço atuais.
    if (margemInput && !(Number.parseFloat(margemInput.value) > 0)) {
        atualizarMargemLucro(custoInput, margemInput, vendaInput);
    }
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
        // Loja sem categorias: já mostra o campo de nova categoria, mas sem roubar o foco do nome.
        selectCategoria.value = '__novo__';
        tratarMudancaCategoria(selectCategoria, false);
    }
}

function tratarMudancaCategoria(select, focar = true) {
    const inputNova = document.getElementById('input-nova-categoria');
    if (!inputNova) return;
    // Só um dos dois campos pode se chamar "categoria": com os dois, o Django fica com o último
    // (o campo de nova categoria, vazio) e a categoria escolhida na lista se perdia.
    if (select.value === '__novo__') {
        select.removeAttribute('name');
        inputNova.setAttribute('name', 'categoria');
        // Categoria é opcional: nova categoria em branco = produto sem categoria.
        inputNova.classList.remove('hidden');
        if (focar) inputNova.focus();
    } else {
        select.setAttribute('name', 'categoria');
        inputNova.removeAttribute('name');
        inputNova.classList.add('hidden');
        inputNova.value = '';
    }
}

/* Avisa antes do envio se as fotos escolhidas passam do limite do produto (o servidor também confere). */
function limitarFotos(input) {
    const maximo = Number(input.dataset.maximoFotos);
    const removidas = (document.getElementById('remover_imagens')?.value || '').split(',');
    const atuais = [...document.querySelectorAll('#container-imagens-atuais [data-id]')]
        .filter((foto) => !removidas.includes(foto.dataset.id)).length;
    const disponiveis = Math.max(0, maximo - atuais);

    let mensagem = '';
    if (input.files.length > disponiveis) {
        const detalhe = disponiveis ? `Dá para adicionar mais ${disponiveis}.` : 'Remova alguma antes de adicionar outra.';
        mensagem = `Cada produto pode ter no máximo ${maximo} fotos. ${detalhe}`;
    }
    input.setCustomValidity(mensagem);
    if (mensagem) input.reportValidity();
}

function marcarParaRemover(id, wrapper) {
    const inputRemover = document.getElementById('remover_imagens');
    const idsAtuais = inputRemover.value ? inputRemover.value.split(',') : [];
    
    if (!idsAtuais.includes(id)) {
        idsAtuais.push(id);
        inputRemover.value = idsAtuais.join(',');
    }
    // Remover uma foto libera espaço: confere de novo as fotos já escolhidas para enviar.
    const inputFotos = document.querySelector('[data-maximo-fotos]');
    if (inputFotos) limitarFotos(inputFotos);

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
    if (btnAnt) btnAnt.style.display = exibirControles ? '' : 'none';
    if (btnProx) btnProx.style.display = exibirControles ? '' : 'none';
}

function fecharModalDireto() {
    const modal = document.getElementById('modal-imagem');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

/* istanbul ignore else */
if (typeof module !== 'undefined') {
    module.exports = { 
        tratarMudancaCategoria, 
        marcarParaRemover, 
        limitarFotos,
        abrirModalEdicaoCliente, 
        fecharModalEdicaoCliente,
        fecharModalDireto,
        abrirModalGaleria,
        mudarImagem
    };
}