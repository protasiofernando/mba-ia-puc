#!/usr/bin/env python3
"""
Análise exploratória de categorias de chamados
Identifica padrões, atributos e agrupa tipos similares
"""

import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Any, Union
from collections import Counter

from data_loader import load_jira_data

class CategoryAnalyzer:
    """Analisa e categoriza chamados JIRA"""

    def __init__(self, csv_paths: Union[str, List[str], None] = None):
        self.csv_paths = csv_paths
        self.df = None
        self.categories = {}

    def load_data(self) -> pd.DataFrame:
        """Carrega dados dos CSVs"""
        print(f"📂 Carregando dados dos CSVs do Jira...")
        self.df = load_jira_data(self.csv_paths)
        return self.df
    
    def analyze_categories(self) -> Dict[str, Any]:
        """
        Analisa categorias e tipos de chamados
        Mapeia padrões, atributos obrigatórios, frequência
        """
        print("\n🔍 Analisando categorias...")
        
        self.categories = {}
        
        # Agrupa por tipo de solicitação
        grouped = self.df.groupby('Customer Request Type')
        
        for category_name, group in grouped:
            self.categories[category_name] = {
                "total": len(group),
                "resolvidos": len(group[group['Situação'] == 'Resolvido']),
                "tempo_medio_horas": float(group['Tempo total conclusão'].mean()),
                "tempo_max_horas": float(group['Tempo total conclusão'].max()),
                "tempo_min_horas": float(group['Tempo total conclusão'].min()),
                "interacoes_media": float(group['qtd_interacoes'].mean()),
                "taxa_resolucao": float(len(group[group['Situação'] == 'Resolvido']) / len(group) * 100),
                "exemplos": group['Resumo'].head(3).tolist()
            }
        
        return self.categories
    
    def identify_attributes(self) -> Dict[str, List[str]]:
        """
        Identifica atributos obrigatórios por categoria
        Analisa quais campos são sempre preenchidos
        """
        print("\n📋 Identificando atributos obrigatórios...")
        
        mandatory_attrs = {}
        
        for category in self.df['Customer Request Type'].unique():
            category_data = self.df[self.df['Customer Request Type'] == category]
            
            attrs = {
                "titulo": not category_data['Resumo'].isna().any(),
                "descricao": not category_data['Descrição'].isna().any(),
                "responsavel": not category_data['Responsável'].isna().any(),
                "tipo_solicitacao": not category_data['Customer Request Type'].isna().any(),
                "solicitante": not category_data['Solicitante'].isna().any()
            }
            
            mandatory_attrs[category] = {
                "total_chamados": len(category_data),
                "atributos_preenchidos": attrs,
                "atributos_obrigatorios": [k for k, v in attrs.items() if v]
            }
        
        return mandatory_attrs
    
    def extract_keywords(self) -> Dict[str, List[tuple]]:
        """Extrai palavras-chave mais frequentes por categoria"""
        print("\n🔑 Extraindo palavras-chave por categoria...")
        
        keywords = {}
        
        for category in self.df['Customer Request Type'].unique():
            category_data = self.df[self.df['Customer Request Type'] == category]
            
            # Combina resumos e descrições
            all_text = " ".join(category_data['Resumo'].fillna(""))
            
            # Quebra em palavras e filtra
            words = all_text.lower().split()
            stop_words = {'de', 'para', 'em', 'e', 'o', 'a', 'que', 'do', 'da', 'os', 'as', 
                         'na', 'no', 'nas', 'nos', 'com', 'por', 'um', 'uma', 'uns', 'umas'}
            
            filtered_words = [w.strip('.,!?;:') for w in words if len(w) > 3 and w not in stop_words]
            word_freq = Counter(filtered_words).most_common(10)
            
            keywords[category] = word_freq
        
        return keywords
    
    def generate_questions(self) -> Dict[str, List[str]]:
        """Gera perguntas orientativas por categoria"""
        print("\n❓ Gerando perguntas orientativas...")
        
        questions_map = {
            "Acesso à bases de dados": [
                "Qual é o sistema específico que precisa acessar?",
                "Qual ambiente? (Desenvolvimento, Homologação, Produção)",
                "Já tem credenciais de acesso ou é primeira vez?",
                "Qual nível de permissão é necessário? (Leitura, Escrita, Admin)",
                "Existe urgência/prazo crítico para este acesso?"
            ],
            "Acesso ao portal/plataforma": [
                "Qual portal exatamente?",
                "Qual é o seu papel/departamento?",
                "Esse é acesso novo ou restauração?",
                "Precisa acessar de qual localização? (Interna/Externa/VPN)",
                "Quando precisa desse acesso operacional?"
            ],
            "Instalação de pacotes": [
                "Em qual servidor? (Produção, Dev, Teste)",
                "Qual versão específica do pacote?",
                "Existem dependências adicionais?",
                "Qual linguagem/plataforma? (Python, R, Node, etc)",
                "Precisa testar em ambiente de teste primeiro?"
            ],
            "Atendimento de Incidentes": [
                "O sistema está completamente indisponível ou funcionando parcialmente?",
                "Quantos usuários são afetados?",
                "Quando o problema começou?",
                "Qual é o mensagem de erro específica?",
                "Já foi feito algum troubleshooting básico?"
            ],
            "Análise de custos de nuvem": [
                "Qual serviço específico? (VM, Storage, Banco de dados, etc)",
                "Qual período analisar? (Último mês, últimos 3 meses)",
                "Qual é a meta de redução de custos?",
                "Existem restrições orçamentárias?",
                "Quem é o responsável pelo orçamento?"
            ],
            "Dúvidas sobre produtos da nuvem": [
                "Qual produto específico? (Azure, AWS, Google Cloud, etc)",
                "Qual é a dúvida específica? (Configuração, Pricing, Capacidade)",
                "Você tem documentação que consultou?",
                "É bloqueante para produção?",
                "Qual é o contexto de uso? (Nova implementação, Troubleshooting)"
            ],
            "Solicitar suporte para laboratório virtual": [
                "Qual laboratório/ambiente virtual?",
                "Qual é o problema exato? (Performance, Conexão, Aplicação)",
                "Quantos usuários afetados?",
                "Qual é a criticidade? (Bloqueante, Importante, Baixa)",
                "Qual é o SLA esperado?"
            ],
            "Migração": [
                "Migração de qual para qual tecnologia/plataforma?",
                "Existe janela de downtime prevista?",
                "Qual é a data alvo para migração?",
                "Quem valida se a migração foi bem-sucedida?",
                "Existem dados que precisam ser preservados especialmente?"
            ],
            "Configuração de firewall": [
                "Qual regra de firewall exatamente?",
                "Origem IP e Destino IP?",
                "Protocolo e porta específica?",
                "Qual é a justificativa de negócio?",
                "É permanente ou temporário?"
            ],
        }
        
        # Para categorias não mapeadas, gera genérico
        for category in self.df['Customer Request Type'].unique():
            if category not in questions_map:
                questions_map[category] = [
                    "Qual é o problema ou necessidade específica?",
                    "Qual é o impacto para o negócio?",
                    "Qual é o prazo necessário?",
                    "Já foi tentada alguma solução?",
                    "Quem é o responsável por validar a resolução?"
                ]
        
        return questions_map
    
    def save_analysis(self, output_path: str = None) -> str:
        """Salva análise em JSON"""
        if output_path is None:
            output_path = Path(__file__).parent / "analise_categorias.json"
        
        output_path = Path(output_path)
        
        analysis = {
            "categorias": self.categories,
            "timestamp": pd.Timestamp.now().isoformat()
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"✅ Análise salva em: {output_path}")
        return str(output_path)
    
    def print_report(self):
        """Printa relatório resumido"""
        print("\n" + "="*70)
        print("📊 ANÁLISE DE CATEGORIAS - RELATÓRIO")
        print("="*70)
        
        for category, data in sorted(self.categories.items(), key=lambda x: x[1]['total'], reverse=True):
            print(f"\n🏷️  {category}")
            print(f"   Total: {data['total']} | Resolvidos: {data['resolvidos']} ({data['taxa_resolucao']:.1f}%)")
            print(f"   ⏱️  Tempo médio: {data['tempo_medio_horas']:.1f}h (min: {data['tempo_min_horas']:.1f}h, máx: {data['tempo_max_horas']:.1f}h)")
            print(f"   💬 Interações: {data['interacoes_media']:.1f}")
            print(f"   Exemplos:")
            for ex in data['exemplos']:
                print(f"      - {ex[:60]}...")


def main():
    analyzer = CategoryAnalyzer()
    analyzer.load_data()
    analyzer.analyze_categories()
    analyzer.print_report()
    analyzer.save_analysis()


if __name__ == "__main__":
    main()
